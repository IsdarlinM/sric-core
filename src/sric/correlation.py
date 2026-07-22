from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class CorrelationFact(BaseModel):
    model_config=ConfigDict(extra="forbid")
    fact_id:str;fact_type:str;value:str;source:str
    evidence_ids:list[str]=Field(default_factory=list);counter_evidence_ids:list[str]=Field(default_factory=list)
    observed_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc));source_group:str|None=None
    attributes:dict[str,Any]=Field(default_factory=dict)

class SignalContribution(BaseModel):
    model_config=ConfigDict(extra="forbid")
    signal:str;fact_ids:list[str];contribution:float=Field(ge=-1,le=1);reason:str

class CorrelationResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    rule_id:str;title:str;status:str="HYPOTHESIS";confidence:float=Field(ge=0,le=1);fact_ids:list[str]
    evidence_ids:list[str]=Field(default_factory=list);counter_evidence:list[str]=Field(default_factory=list)
    contributions:list[SignalContribution]=Field(default_factory=list);source_independence:float=Field(default=0,ge=0,le=1)
    temporal_relevance:float=Field(default=1,ge=0,le=1);missing_evidence:list[str]=Field(default_factory=list);explanation:list[str]=Field(default_factory=list)

@dataclass(frozen=True)
class CorrelationRule:
    rule_id:str;title:str;evaluator:Callable[[list[CorrelationFact]],CorrelationResult|None]

class DeclarativeCorrelationRule(BaseModel):
    model_config=ConfigDict(extra="forbid")
    rule_id:str;title:str;requires:list[str];optional:list[str]=Field(default_factory=list);base_confidence:float=Field(default=.35,ge=0,le=1);per_independent_source:float=Field(default=.08,ge=0,le=.5);output_status:str="HYPOTHESIS"
    def evaluate(self,facts:list[CorrelationFact])->CorrelationResult|None:
        by_type={t:[f for f in facts if f.fact_type==t] for t in {*self.requires,*self.optional}}
        if any(not by_type.get(t) for t in self.requires):return None
        used=[f for t in self.requires+self.optional for f in by_type.get(t,[])];groups={f.source_group or f.source for f in used};independence=min(1.0,len(groups)/max(1,len(used)))
        now=datetime.now(timezone.utc);ages=[]
        for f in used:
            dt=f.observed_at if f.observed_at.tzinfo else f.observed_at.replace(tzinfo=timezone.utc);ages.append(max(0,(now-dt).days))
        temporal=max(0.1,1.0-(sum(ages)/max(1,len(ages)))/3650)
        counter=sorted({e for f in used for e in f.counter_evidence_ids});confidence=min(.95,self.base_confidence+self.per_independent_source*len(groups)+.03*sum(bool(by_type.get(t)) for t in self.optional));confidence=max(.05,confidence-.05*len(counter));confidence*=temporal
        contributions=[SignalContribution(signal=t,fact_ids=[f.fact_id for f in by_type.get(t,[])],contribution=.1 if by_type.get(t) else 0,reason="required signal observed" if t in self.requires else "optional signal observed") for t in self.requires+self.optional if by_type.get(t)]
        missing=[t for t in self.optional if not by_type.get(t)]
        return CorrelationResult(rule_id=self.rule_id,title=self.title,status=self.output_status,confidence=round(confidence,4),fact_ids=[f.fact_id for f in used],evidence_ids=sorted({e for f in used for e in f.evidence_ids}),counter_evidence=counter,contributions=contributions,source_independence=round(independence,4),temporal_relevance=round(temporal,4),missing_evidence=missing,explanation=[f"Independent source groups: {len(groups)}",f"Counter-evidence items: {len(counter)}","Correlation result remains a candidate and never validates a finding."])

class CorrelationEngine:
    def __init__(self)->None:self._rules:dict[str,CorrelationRule|DeclarativeCorrelationRule]={}
    def register(self,rule:CorrelationRule|DeclarativeCorrelationRule)->None:
        if rule.rule_id in self._rules:raise ValueError(f"duplicate correlation rule: {rule.rule_id}")
        self._rules[rule.rule_id]=rule
    def evaluate(self,facts:list[CorrelationFact])->list[CorrelationResult]:
        out=[]
        for rid in sorted(self._rules):
            rule=self._rules[rid]
            result=rule.evaluate(facts) if isinstance(rule, DeclarativeCorrelationRule) else rule.evaluator(facts)
            if result is not None:out.append(result)
        return out

def historical_active_relevance_rule()->CorrelationRule:
    def evaluate(facts:list[CorrelationFact])->CorrelationResult|None:
        historical=[f for f in facts if f.fact_type=="historical_endpoint"];dns=[f for f in facts if f.fact_type=="current_dns"];auth=[f for f in facts if f.fact_type=="auth_observation"]
        if not historical or not dns:return None
        all_facts=historical+dns+auth;sources={f.source_group or f.source for f in all_facts};confidence=min(.9,.45+.12*len(sources)+(.12 if auth else 0))
        return CorrelationResult(rule_id="historical-active-relevance",title="Historical endpoint may retain current security relevance",confidence=confidence,fact_ids=[f.fact_id for f in all_facts],evidence_ids=sorted({e for f in all_facts for e in f.evidence_ids}),counter_evidence=sorted({e for f in all_facts for e in f.counter_evidence_ids}),source_independence=min(1,len(sources)/len(all_facts)),missing_evidence=[] if auth else ["auth_observation"],explanation=["Historical endpoint evidence exists.","Current DNS evidence exists.","Authorization behavior is present." if auth else "Authorization relevance is UNKNOWN."])
    return CorrelationRule("historical-active-relevance","Historical endpoint may retain current security relevance",evaluate)
