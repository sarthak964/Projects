from app.services.verification_nodes import check_checklist_node

# Only a clear "supports" counts as genuine. Anything else (unclear, irrelevant,
# contradicts, no_photo) sends the reviewer back to re-upload, which penalizes
# nobody.
GENUINE_PHOTO_CHECKS = {"supports"}


def check_photos(items: list[str], notes: str, photos: list[dict]) -> dict:
    """
    Runs the vision check on only the photos for the items the renter rejected.
    Returns {"all_genuine": bool, "items": [...]}.
    """
    state = {
        "job_id": 0,
        "checklist": items,
        "photos": photos,
        "notes": notes,
        "verification_result": [],
        "all_addressed": False,
        "check_score": 0.0,
        "summary": "",
    }
    raw_results = check_checklist_node(state)["verification_result"]
    by_item = {r["item"]: r for r in raw_results}

    results = []
    for item in items:
        r = by_item.get(item)
        photo_check = r["photo_check"] if r else "no_photo"
        results.append(
            {
                "item": item,
                "photo_check": photo_check,
                "observation": r.get("photo_observation", "") if r else "",
                "reasoning": r["reasoning"] if r else "The AI returned no result for this item",
                "genuine": photo_check in GENUINE_PHOTO_CHECKS,
            }
        )

    return {"all_genuine": all(x["genuine"] for x in results), "items": results}
