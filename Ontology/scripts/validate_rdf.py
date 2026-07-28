from pathlib import Path

from pyshacl import validate
from rdflib import Graph


def validate_rdf(data_path: Path, shapes_path: Path) -> tuple[bool, str]:
    data = Graph().parse(data_path, format="turtle")
    shapes = Graph().parse(shapes_path, format="turtle")
    conforms, _, report = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="rdfs",
        meta_shacl=True,
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )
    return bool(conforms), str(report)
