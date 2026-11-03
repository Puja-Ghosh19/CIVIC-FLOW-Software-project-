import re

# Words that show what the person wants. Matching uses whole words/phrases only.
NID_WORDS = ["nid", "national id", "national identity", "voter id", "smart card", "id card"]
CORRECTION_WORDS = ["correct", "correction", "change", "wrong", "mistake", "spelling", "update", "fix", "error", "edit", "misspelled"]
LOST_WORDS = ["lost", "lose", "missing", "misplaced", "stolen", "damaged", "burnt", "burned", "can't find", "cannot find", "do not have", "don't have", "dont have", "no longer have"]
CERT_WORDS = ["ssc", "hsc", "certificate", "marksheet", "mark sheet", "transcript", "testimonial", "academic"]


def _has(text, words):
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text) for w in words)


def _result(services, name, reason, tips=None):
    tips = list(tips or [])
    if name != "No direct match found" and not tips:
        tips.append("Open the service details to see every required document and the steps to follow, then continue to your application when you are ready.")
    sid = None
    for s in services or []:
        if s["name"] == name:
            sid = s["id"]
            break
    return {"id": sid, "name": name, "reason": reason, "tips": tips[:5]}



# Extra advice that is shown whenever the description mentions one of these topics.
# Each topic is (required-all word groups, tips). A group matches if ANY word in it is found.
TOPICS = [
    ([["nid", "national id", "voter id", "id card"], LOST_WORDS],
     ["Lost NID card: report the loss to the police (GD), then ask your Upazila/Thana Election Office or the NID Wing (nidw.gov.bd) about a replacement card."]),
    ([["passport", "e-passport", "epassport"], LOST_WORDS],
     ["Lost passport: file a GD at the police station first, then contact the passport office about a re-issue. Bring your NID and the GD copy."]),
    ([["birth certificate", "birth registration", "birth cert"], LOST_WORDS],
     ["Lost birth certificate: if you know your 17-digit birth registration number, you can usually get a copy from the Registrar's office or the birth registration website (bdris.gov.bd)."]),
    ([["ssc", "hsc", "marksheet", "mark sheet", "transcript", "testimonial", "academic certificate", "education certificate"], LOST_WORDS],
     ["Lost SSC/HSC certificate: ask your school/college or the Education Board for a duplicate or certified copy. They usually ask for a General Diary (GD), an application, your ID and a fee. Check the exact list with the board.",
      "For an NID, a lost certificate does not have to stop you. Ask your Upazila/Thana Election Office which other proof of age and education they accept (for example your birth registration certificate, passport or a signed proof copy)."]),
    ([["name", "spelling", "date of birth", "dob", "birth date", "father", "mother", "wrong", "mistake", "misspelled"], ["wrong", "mistake", "error", "incorrect", "different", "mismatch", "spelling", "misspelled", "correct", "correction", "change"]],
     ["Wrong information: first find a document that proves the correct detail (SSC certificate, birth certificate or passport). Offices compare your documents, so try to make your birth certificate, SSC and NID match each other."]),
    ([["address", "moved", "shifted", "relocated", "permanent address", "present address"], ["change", "update", "new", "moved", "shifted", "correct", "correction", "wrong"]],
     ["Address change: bring proof of the new address such as a recent utility bill, holding tax receipt or rent agreement, and apply for an NID information correction."]),
    ([["fee", "fees", "cost", "price", "charge", "how much", "pay", "payment"]],
     ["Fees: government fees vary and can change. The service page shows the fee information, and you should always confirm the latest amount on the official website or office before paying."]),
    ([["how long", "time", "days", "urgent", "urgently", "fast", "quick", "express", "deadline", "hurry"]],
     ["Time: the days shown on each service are estimates only. Some services, like the passport, have faster delivery options for an extra fee. Start early and keep all receipts."]),
    ([["document", "documents", "papers", "require", "required", "requirement", "requirements", "need to bring", "checklist"]],
     ["Documents: open the service details page for the full checklist of required and optional documents, with step-by-step instructions."]),
    ([["age", "years old", "year old", "minor", "under 18", "16", "17", "18", "teen", "teenager", "child"]],
     ["Age: the Election Commission has started NID registration for citizens aged 16 and above, and they become voters at 18. Confirm the current age rule with your local Election Office."]),
    ([["no documents", "don't have any", "dont have any", "do not have any", "nothing", "no papers", "no certificate"]],
     ["Starting from nothing: begin with your birth registration certificate, because most other services ask for it. Then apply for your NID, then other services."]),
    ([["abroad", "overseas", "expatriate", "outside bangladesh", "foreign", "living in"]],
     ["Living abroad: the Election Commission offers NID services through some Bangladesh embassies and high commissions. Check your nearest mission for the current list."]),
]


def topic_tips(t):
    tips = []
    for groups, advice in TOPICS:
        if all(_has(t, g) for g in groups):
            for a in advice:
                if a not in tips:
                    tips.append(a)
    return tips


def find_service(problem, services=None):
    """Suggest a service for the person's description. `services` is the list of rows from the database."""
    t = " ".join(problem.lower().replace("’", "'").split())
    tips = topic_tips(t)
    lost = _has(t, LOST_WORDS)

    if _has(t, NID_WORDS):
        if lost and not _has(t, ["new", "apply", "first time", "first-time", "get", "make"]) and not _has(t, CERT_WORDS):
            return _result(services, "No direct match found",
                           "It sounds like you lost your NID card. A replacement (reissue) is not covered by this demo yet.", tips)
        if _has(t, CORRECTION_WORDS):
            return _result(services, "NID Information Correction",
                           "You mentioned fixing information on your NID.", tips)
        return _result(services, "NID Application (New NID)",
                       "You need a new NID card, so the new NID application guide fits best." + (" Your lost certificate is covered in the tips below." if tips else ""), tips)

    if _has(t, ["birth", "birth certificate", "birth registration"]):
        tip = ["This guide covers corrections. To register a new birth, start on the official birth registration website (bdris.gov.bd)."]
        return _result(services, "Birth Certificate Correction", "Your description is about a birth certificate.", tip + tips)
    if _has(t, ["passport", "e-passport", "epassport"]):
        return _result(services, "Passport Application", "Your description matches the passport service.", tips)
    if _has(t, ["trade", "trade license", "business license", "shop license", "business"]):
        return _result(services, "Trade License", "Your description matches the trade license service.", tips)

    # No service matched: still give useful guidance, whatever the person wrote.
    general = ["To get a better match, describe the document or service and what happened. For example: \"I want a new NID\", \"my name is spelled wrong on my passport\" or \"I lost my birth certificate\"."]
    if tips:
        return _result(services, "No direct match found",
                       "We could not tell exactly which service you need, but these tips may help.", tips)
    return _result(services, "No direct match found",
                   "We could not find an exact service for that, but you can pick one below or browse all services.", general)
