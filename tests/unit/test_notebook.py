from sric.notebook import NotebookEntry, ResearchNotebook


def test_notebook_and_saved_queries(tmp_path):
    n=ResearchNotebook(tmp_path)
    e=n.add(NotebookEntry(entry_type="observation", title="A", body="B"))
    assert n.list()[0].entry_id == e.entry_id
    n.save_query("legacy", "oauth issuer")
    assert n.saved_queries() == [{"name":"legacy","query":"oauth issuer"}]
