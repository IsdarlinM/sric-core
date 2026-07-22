from __future__ import annotations

import operator
import shlex
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .graph import TemporalGraph


class GraphQueryError(ValueError): pass


@dataclass(frozen=True)
class QueryPlan:
    node_type: str
    label: str | None
    edge_type: str | None
    target_type: str | None
    confidence_op: str | None
    confidence_value: float | None
    at: datetime | None
    limit: int
    offset: int


class SecurityResearchGraphQuery:
    """Strict deterministic read-only graph query language with bounded complexity."""
    MAX_QUERY_CHARS=4096; MAX_TOKENS=64; MAX_LIMIT=500
    OPS: dict[str,Callable[[float,float],bool]]={">=":operator.ge,">":operator.gt,"<=":operator.le,"<":operator.lt,"=":operator.eq,"==":operator.eq}
    def __init__(self,graph:TemporalGraph)->None:self.graph=graph
    def parse(self,expression:str)->QueryPlan:
        if len(expression)>self.MAX_QUERY_CHARS: raise GraphQueryError("query exceeds maximum length")
        try: tokens=shlex.split(expression)
        except ValueError as exc: raise GraphQueryError(f"invalid query quoting: {exc}") from exc
        if len(tokens)>self.MAX_TOKENS: raise GraphQueryError("query exceeds complexity limit")
        if len(tokens)<2 or tokens[0].upper()!="MATCH": raise GraphQueryError("query must start with MATCH <node_type|*>")
        node_type=tokens[1]; label=edge_type=target_type=op=None; conf=None; at=None; limit=100; offset=0; idx=2
        while idx<len(tokens):
            keyword=tokens[idx].upper()
            if keyword=="LABEL":
                if idx+1>=len(tokens):raise GraphQueryError("LABEL requires text")
                label=tokens[idx+1];idx+=2
            elif keyword=="EDGE":
                if idx+3>=len(tokens) or tokens[idx+2].upper()!="TO":raise GraphQueryError("EDGE requires: EDGE <edge_type|*> TO <node_type|*>")
                edge_type=tokens[idx+1];target_type=tokens[idx+3];idx+=4
            elif keyword=="WHERE":
                if idx+3>=len(tokens) or tokens[idx+1].lower()!="confidence":raise GraphQueryError("WHERE currently supports: WHERE confidence <op> <0..1>")
                op=tokens[idx+2]
                if op not in self.OPS:raise GraphQueryError("unsupported confidence operator")
                try:conf=float(tokens[idx+3])
                except ValueError as exc:raise GraphQueryError("confidence must be numeric") from exc
                if not 0<=conf<=1:raise GraphQueryError("confidence must be between 0 and 1")
                idx+=4
            elif keyword=="AT":
                if idx+1>=len(tokens):raise GraphQueryError("AT requires ISO-8601 timestamp")
                try:at=datetime.fromisoformat(tokens[idx+1].replace("Z","+00:00"))
                except ValueError as exc:raise GraphQueryError("AT requires a valid ISO-8601 timestamp") from exc
                idx+=2
            elif keyword=="LIMIT":
                if idx+1>=len(tokens):raise GraphQueryError("LIMIT requires integer")
                try:limit=int(tokens[idx+1])
                except ValueError as exc:raise GraphQueryError("LIMIT requires integer") from exc
                if not 1<=limit<=self.MAX_LIMIT:raise GraphQueryError(f"LIMIT must be 1..{self.MAX_LIMIT}")
                idx+=2
            elif keyword=="OFFSET":
                if idx+1>=len(tokens):raise GraphQueryError("OFFSET requires integer")
                try:offset=int(tokens[idx+1])
                except ValueError as exc:raise GraphQueryError("OFFSET requires integer") from exc
                if offset<0 or offset>100000:raise GraphQueryError("OFFSET out of range")
                idx+=2
            else: raise GraphQueryError(f"unsupported query keyword: {tokens[idx]}")
        return QueryPlan(node_type,label,edge_type,target_type,op,conf,at,limit,offset)
    def explain_plan(self,expression:str)->dict[str,Any]:return {"mode":"READ_ONLY","plan":self.parse(expression).__dict__,"mutations":False}
    def execute(self,expression:str)->dict[str,Any]:
        plan=self.parse(expression);snap=self.graph.snapshot(plan.at);nodes=snap["nodes"];edges=snap["edges"]
        def conf_ok(item:dict[str,Any])->bool:
            if plan.confidence_op is None or plan.confidence_value is None:return True
            return self.OPS[plan.confidence_op](float(item.get("confidence",0.0)),plan.confidence_value)
        matched=[n for n in nodes if (plan.node_type=="*" or str(n.get("node_type","")).casefold()==plan.node_type.casefold()) and (plan.label is None or plan.label.casefold() in str(n.get("label","")).casefold()) and conf_ok(n)]
        if plan.edge_type is None:
            page=matched[plan.offset:plan.offset+plan.limit];return {"query":expression,"mode":"READ_ONLY","total":len(matched),"offset":plan.offset,"limit":plan.limit,"nodes":page,"edges":[]}
        ids={str(n["node_id"]) for n in matched};by_id={str(n["node_id"]):n for n in nodes};matched_edges=[];targets={}
        for edge in edges:
            if str(edge.get("source_node_id")) not in ids:continue
            if plan.edge_type!="*" and str(edge.get("edge_type","")).casefold()!=str(plan.edge_type).casefold():continue
            if not conf_ok(edge):continue
            target=by_id.get(str(edge.get("target_node_id")))
            if target is None or (plan.target_type!="*" and str(target.get("node_type","")).casefold()!=str(plan.target_type).casefold()):continue
            matched_edges.append(edge);targets[str(target["node_id"])]=target
        page_edges=matched_edges[plan.offset:plan.offset+plan.limit];page_target_ids={str(e["target_node_id"]) for e in page_edges}
        return {"query":expression,"mode":"READ_ONLY","total":len(matched_edges),"offset":plan.offset,"limit":plan.limit,"nodes":matched,"edges":page_edges,"targets":[targets[x] for x in sorted(page_target_ids) if x in targets]}
