"""Tagging and retrieval evaluation against the local library."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from app.db.models import Chunk, Material
from app.db.session import SessionLocal, init_db
from app.knowledge.seed import seed_knowledge_tree
from app.rag.embeddings import get_embedding_service
from app.rag.index import search_knowledge
from app.rag.tagging import load_prepared_points, tag_text_multi
from app.services.ingestion import create_sample_material
from app.services.settings_service import load_llm_settings

CASES = ROOT / "evals" / "library_cases.json"


async def _ensure_sample(db) -> None:
    count = (
        await db.execute(
            select(func.count(Chunk.id))
            .join(Material, Chunk.material_id == Material.id)
            .where(Material.status == "ready")
        )
    ).scalar() or 0
    if count:
        return
    material = await create_sample_material(db)
    for _ in range(60):
        await asyncio.sleep(0.5)
        await db.refresh(material)
        if material.status in {"ready", "failed"}:
            return


async def main() -> int:
    await init_db()
    payload = json.loads(CASES.read_text())
    tagging_cases = payload.get("tagging", [])
    retrieval_cases = payload.get("retrieval", [])

    async with SessionLocal() as db:
        await seed_knowledge_tree(db)
        llm = await load_llm_settings(db)
        embedder = get_embedding_service(llm)
        prepared = await load_prepared_points(db)
        profiles = [item.profile or item.point.name for item in prepared]
        vectors = await embedder.embed(profiles) if profiles else []
        point_embeddings = {
            item.point.id: vector
            for item, vector in zip(prepared, vectors, strict=False)
        }

        top1 = 0
        top3 = 0
        type_hits = 0
        failures: list[dict] = []
        for case in tagging_cases:
            embedding = (await embedder.embed([case["text"]]))[0]
            result = tag_text_multi(
                case["text"],
                prepared,
                embedding=embedding,
                point_embeddings=point_embeddings,
            )
            label_ids = [
                label.knowledge_point_id for label in result.labels
            ]
            if result.knowledge_point_id == case["expected_kp"]:
                top1 += 1
            if case["expected_kp"] in label_ids:
                top3 += 1
            if result.chunk_type == case["expected_type"]:
                type_hits += 1
            else:
                failures.append(
                    {
                        "text": case["text"][:80],
                        "expected_type": case["expected_type"],
                        "actual_type": result.chunk_type,
                        "expected_kp": case["expected_kp"],
                        "actual_kp": result.knowledge_point_id,
                    }
                )

        await _ensure_sample(db)
        retrieval_hits = 0
        retrieval_failures: list[dict] = []
        for case in retrieval_cases:
            result = await search_knowledge(
                db, case["query"], embedder, top_k=5
            )
            found = False
            for hit in result["chunks"]:
                ids = {hit.get("knowledge_point_id")}
                ids.update(
                    label.get("knowledge_point_id")
                    for label in hit.get("labels") or []
                )
                if case["expected_kp"] in ids:
                    found = True
                    break
            if found:
                retrieval_hits += 1
            else:
                retrieval_failures.append(case)

    tag_total = max(len(tagging_cases), 1)
    retrieval_total = max(len(retrieval_cases), 1)
    metrics = {
        "tagging": {
            "cases": tag_total,
            "top1_accuracy": round(top1 / tag_total, 3),
            "label_recall_at_3": round(top3 / tag_total, 3),
            "chunk_type_accuracy": round(type_hits / tag_total, 3),
            "failures": failures,
        },
        "retrieval": {
            "cases": retrieval_total,
            "recall_at_5": round(retrieval_hits / retrieval_total, 3),
            "failures": retrieval_failures,
        },
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    ok = (
        metrics["tagging"]["top1_accuracy"] >= 0.70
        and metrics["tagging"]["chunk_type_accuracy"] >= 0.70
        and metrics["retrieval"]["recall_at_5"] >= 0.70
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
