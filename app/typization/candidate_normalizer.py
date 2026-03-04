from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List


NOISE_LABELS = {
    "КОРОТКО",
    "ОСНОВНІ",
    "ДОДАТКОВІ",
    "ФАКТИЧНО",
    "СЬОГОДНІ",
    "ФАКТИЧНА",
    "СИТУАЦІЯ",
}

DOMAIN_PROMOTE_HINTS = {
    "обладнання",
    "виробництва",
    "комунікації",
    "продуктивність",
    "продуктивністі",
    "сировини",
    "інвестиційна",
    "беззбитковості",
    "масштабування",
}

SOFT_NOISE_TERMS = {
    "початок",
    "частини",
    "розподіленний",
    "участки",
    "участків",
    "площадки",
    "розміщення",
    "підбір",
    "закупка",
    "доставка",
    "монтаж",
    "тестовий",
    "гібридному",
    "форматі",
    "використання",
    "робота",
    "оптимізація",
    "виходу",
    "готової",
    "продукції",
    "стабілізація",
    "контрольований",
    "контроль",
    "якості",
    "розвиток",
    "знаходиться",
    "стадії",
    "запуск",
    "участка",
    "порушення",
    "внутрішньої",
    "фінансова",
    "стабільність",
    "виконання",
    "домовленостей",
    "пріоритеті",
}

WORD_RE = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_\\-]+")


class CandidateNormalizer:
    def normalize(
        self,
        proposals: List[Dict],
        claims: List[Dict],
        known_types: List[Dict],
    ) -> Dict:
        claim_text = " ".join(c.get("text", "") for c in claims).lower()
        token_counts = Counter(WORD_RE.findall(claim_text))

        known_alias_index = []
        for t in known_types:
            for alias in t.get("aliases", []):
                known_alias_index.append((alias.lower(), t["type_id"], t["name"]))

        promote_to_known = []
        map_to_existing = []
        deprecate = []
        keep_candidate = []

        for p in proposals:
            label = str(p.get("label", "")).strip()
            label_low = label.lower()
            candidate_id = str(p.get("candidate_id", ""))

            if not label:
                deprecate.append(
                    {
                        "candidate_id": p.get("candidate_id"),
                        "label": label,
                        "reason": "empty_label",
                    }
                )
                continue

            if candidate_id.startswith("AUTO_CAND_"):
                keep_candidate.append(
                    {
                        "candidate_id": candidate_id,
                        "label": label,
                        "reason": "blocked_by_fpf_demotion",
                    }
                )
                continue

            if label in NOISE_LABELS or len(label_low) <= 4:
                deprecate.append(
                    {
                        "candidate_id": p.get("candidate_id"),
                        "label": label,
                        "reason": "heading_or_short_noise",
                    }
                )
                continue

            mapped = None
            for alias, type_id, type_name in known_alias_index:
                if alias == label_low or (len(alias) > 5 and alias in label_low):
                    mapped = {
                        "candidate_id": p.get("candidate_id"),
                        "label": label,
                        "target_type_id": type_id,
                        "target_type": type_name,
                        "reason": "alias_similarity",
                    }
                    break
            if mapped:
                map_to_existing.append(mapped)
                continue

            freq = token_counts.get(label_low, 0)
            if label_low in SOFT_NOISE_TERMS:
                deprecate.append(
                    {
                        "candidate_id": p.get("candidate_id"),
                        "label": label,
                        "reason": "soft_noise_term",
                    }
                )
                continue

            if label_low in DOMAIN_PROMOTE_HINTS or freq >= 2:
                promote_to_known.append(
                    {
                        "candidate_id": p.get("candidate_id"),
                        "label": label,
                        "suggested_type_id": "T_DOMAIN_EXTENSION",
                        "suggested_type": "DomainExtension",
                        "reason": "domain_signal",
                    }
                )
                continue

            if freq <= 1:
                deprecate.append(
                    {
                        "candidate_id": p.get("candidate_id"),
                        "label": label,
                        "reason": "sparse_singleton_noise",
                    }
                )
                continue

            keep_candidate.append(
                {
                    "candidate_id": p.get("candidate_id"),
                    "label": label,
                    "reason": "insufficient_signal",
                }
            )

        return {
            "summary": {
                "promote_to_known": len(promote_to_known),
                "map_to_existing": len(map_to_existing),
                "deprecate": len(deprecate),
                "keep_candidate": len(keep_candidate),
            },
            "promote_to_known": promote_to_known,
            "map_to_existing": map_to_existing,
            "deprecate": deprecate,
            "keep_candidate": keep_candidate,
        }
