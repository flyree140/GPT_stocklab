from pathlib import Path
from stocklab16.stage import stage

def test_paper_files_staged_without_formal_data_mutation(tmp_path):
    root=Path(__file__).resolve().parents[1]
    out=stage(root, tmp_path/"site")
    for name in ["index.html","lab.html","life19.html","lab-guide.html","assets/paper.mjs","assets/paper-engine.mjs"]:
        assert (out/name).is_file(),name
    assert "封閉試驗室" in (out/"index.html").read_text()
