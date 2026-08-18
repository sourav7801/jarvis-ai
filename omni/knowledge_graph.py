from __future__ import annotations

import json
from pathlib import Path
import time


class KnowledgeGraph:

    def __init__(
        self,
        path,
    ):

        self.path = Path(path)


    def _empty(self):

        return {
            "nodes": {},
            "edges": [],
        }


    def _load(self):

        if not self.path.exists():
            return self._empty()

        try:

            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            data.setdefault(
                "nodes",
                {},
            )

            data.setdefault(
                "edges",
                [],
            )

            return data

        except Exception:
            return self._empty()


    def _save(
        self,
        data,
    ):

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = (
            self.path.with_suffix(
                ".tmp"
            )
        )

        temp.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(
            self.path
        )


    def upsert_node(
        self,
        node_id,
        *,
        kind,
        label,
        attributes=None,
    ):

        node_id = str(
            node_id
        ).strip()

        if not node_id:

            raise ValueError(
                "node_id cannot be empty"
            )

        data = self._load()

        current = data[
            "nodes"
        ].get(
            node_id,
            {},
        )

        merged = dict(
            current.get(
                "attributes",
                {},
            )
        )

        merged.update(
            attributes
            or {}
        )

        node = {
            "node_id": node_id,

            "kind": str(kind),

            "label": str(label),

            "attributes": merged,

            "updated_at":
                time.time(),
        }

        data[
            "nodes"
        ][
            node_id
        ] = node

        self._save(
            data
        )

        return node


    def link(
        self,
        source,
        relation,
        target,
        *,
        attributes=None,
    ):

        data = self._load()

        edge = {
            "source":
                str(source),

            "relation":
                str(relation),

            "target":
                str(target),

            "attributes":
                dict(
                    attributes
                    or {}
                ),

            "updated_at":
                time.time(),
        }

        data[
            "edges"
        ] = [
            existing

            for existing
            in data[
                "edges"
            ]

            if not (
                existing.get(
                    "source"
                )
                == edge[
                    "source"
                ]

                and existing.get(
                    "relation"
                )
                == edge[
                    "relation"
                ]

                and existing.get(
                    "target"
                )
                == edge[
                    "target"
                ]
            )
        ]

        data[
            "edges"
        ].append(
            edge
        )

        self._save(
            data
        )

        return edge


    def get(
        self,
        node_id,
    ):

        return self._load()[
            "nodes"
        ].get(
            str(
                node_id
            )
        )


    def neighbors(
        self,
        node_id,
    ):

        node_id = str(
            node_id
        )

        return tuple(
            edge

            for edge
            in self._load()[
                "edges"
            ]

            if (
                edge.get(
                    "source"
                ) == node_id

                or edge.get(
                    "target"
                ) == node_id
            )
        )


    def stats(self):

        data = self._load()

        return {
            "nodes":
                len(
                    data[
                        "nodes"
                    ]
                ),

            "edges":
                len(
                    data[
                        "edges"
                    ]
                ),
        }
