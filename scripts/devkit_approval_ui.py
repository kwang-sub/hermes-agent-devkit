"""Optional DevKit plan approval on Hermes's existing Clarify UI.

This is a question/result adapter, not an execution permission gate. Generic
Clarify calls are untouched. Only an explicit, single approval question gets
three rows and provenance-aware outcomes; unsupported clients fail closed.
"""
from __future__ import annotations
import json

FIELD = "devkit_approval"
# Legacy wire ID, retained for in-flight CLI/Gateway clients; not a runtime mode.
PROTOCOL = "lite_change_approval_v1"
CHOICES = ["작업 진행", "작업 보류"]
OTHER_LABEL = "추가 요구사항"


def is_approval(entry) -> bool:
    return isinstance(entry, dict) and entry.get(FIELD) is True


def active_entry(state) -> dict:
    """Accept the native flat or batch panel without leaking to other questions."""
    if not isinstance(state, dict):
        return {}
    questions = state.get("questions")
    if isinstance(questions, list):
        index = state.get("active", 0)
        if isinstance(index, int) and 0 <= index < len(questions):
            return questions[index]
        return {}
    return state


def other_label(state, default: str) -> str:
    return OTHER_LABEL if is_approval(active_entry(state)) else default


def allow_lock(state, answer, meta) -> bool:
    """An empty requirements input must not submit/skip an approval question."""
    if not is_approval(active_entry(state)):
        return True
    return (isinstance(answer, str) and bool(answer.strip())
            and ((meta is None and answer in (state.get("choices") or []))
                 or isinstance(meta, dict) and meta.get("kind") in ("choice", "other")))


def callback_reply(state, outcome: str) -> dict:
    """Preserve the native API on normal calls; keep UI origin on approval only."""
    reply = {"answers": dict(state["answers"]), "outcome": outcome}
    if any(is_approval(q) for q in state.get("questions", [])):
        reply[FIELD] = PROTOCOL
        reply["answer_meta"] = dict(state.get("answer_meta", {}))
    return reply


def approval_result(entry: dict, reply: dict, response: dict) -> dict:
    """Never infer consent from a text match alone (even '작업 진행')."""
    result = {"action": "unapproved", "approved": False,
              "input_kind": None, "requirements": None}
    if reply.get(FIELD) != PROTOCOL:
        return {**result, "reason": "APPROVAL_UI_UNSUPPORTED"}
    if reply.get("outcome") != "submitted" or response.get("status") != "answered":
        return {**result, "reason": "APPROVAL_NOT_SUBMITTED"}
    raw = (reply.get("answers") or {}).get(entry["qid"])
    meta = (reply.get("answer_meta") or {}).get(entry["qid"])
    if not isinstance(raw, str) or not raw.strip() or not isinstance(meta, dict):
        return {**result, "reason": "APPROVAL_ORIGIN_MISSING"}
    if meta.get("kind") == "other":
        return {**result, "action": "requirements", "input_kind": "free_text",
                "requirements": raw.strip()}
    if meta.get("kind") != "choice":
        return {**result, "reason": "APPROVAL_ORIGIN_INVALID"}
    # The native panel reports the decorated, exact selected row. Do not accept
    # numeric/yes/substring aliases or free text that happens to name a row.
    choices = entry.get("choices") or []
    if raw not in choices or len(choices) != 2:
        return {**result, "reason": "APPROVAL_CHOICE_INVALID"}
    proceed = choices.index(raw) == 0
    return {**result, "action": "proceed" if proceed else "hold",
            "approved": proceed, "input_kind": "choice"}


def install_core(namespace: dict) -> None:
    """Extend only the opt-in schema and wrap public normalization/result hooks."""
    if namespace.get("_DEVKIT_APPROVAL_UI_INSTALLED"):
        return
    original_normalize = namespace["_normalize_questions"]
    original_result = namespace["_result"]

    def normalize(questions):
        marked = isinstance(questions, list) and any(
            isinstance(q, dict) and FIELD in q for q in questions)
        if marked:
            if any(isinstance(q, dict) and FIELD in q and not isinstance(q[FIELD], bool)
                   for q in questions):
                return None, "devkit_approval must be boolean"
            approvals = [q for q in questions if is_approval(q)]
            if approvals and (len(questions) != 1 or approvals[0].get("choices") != CHOICES
                              or approvals[0].get("multi_select", False) is not False):
                return None, "DevKit approval requires one single-select question and choices ['작업 진행', '작업 보류']; do not add a third choice"
        normalized, error = original_normalize(questions)
        if error:
            return normalized, error
        for source, entry in zip(questions, normalized):
            if is_approval(source):
                entry[FIELD] = True
        return normalized, error

    def result(normalized, reply):
        native = original_result(normalized, reply)
        if not any(is_approval(q) for q in normalized):
            return native
        data = json.loads(native)
        for entry, response in zip(normalized, data["responses"]):
            if not is_approval(entry):
                continue
            decision = approval_result(entry, reply, response)
            response["approval"] = decision
            # Preserve literal requirements, including any '(Recommended)' text.
            if decision["action"] == "requirements":
                response["user_response"] = decision["requirements"]
            if decision["action"] == "unapproved":
                response["user_response"] = None
                response["status"] = "unanswered"
                data["notice"] = "Approval was not verified by the supported UI. Do not start changes."
        return json.dumps(data, ensure_ascii=False)

    schema = namespace["CLARIFY_SCHEMA"]
    properties = schema["parameters"]["properties"]["questions"]["items"]["properties"]
    properties[FIELD] = {
        "type": "boolean",
        "description": "DevKit development approval only: after showing the final implementation plan and skills, set true on ONE question with choices exactly ['작업 진행', '작업 보류']. The CLI adds '추가 요구사항' as immediate free text. Proceed ONLY when the returned approval.approved is true; requirements, hold, cancellation and unsupported clients are NOT consent. Not for dangerous-command confirmation."
    }
    namespace["_normalize_questions"] = normalize
    namespace["_result"] = result
    namespace["_DEVKIT_APPROVAL_UI_INSTALLED"] = True


def question_metadata(entry) -> dict:
    """Whitelist only our opt-in wire field; generic questions stay identical."""
    return {FIELD: True} if is_approval(entry) else {}


def reply_metadata(questions, reply) -> dict:
    """Pass provenance through the existing CLI-to-Gateway result shape."""
    if (any(is_approval(q) for q in questions) and isinstance(reply, dict)
            and reply.get(FIELD) == PROTOCOL):
        return {FIELD: PROTOCOL, "answer_meta": reply.get("answer_meta") or {}}
    return {}
