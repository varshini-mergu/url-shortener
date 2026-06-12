import json
import subprocess

payload = {
  "nonce": "lW-L2ssrbWCEijoNFd6RS",
  "events": [
    {
      "module": 5,
      "step": "reflect",
      "event_type": "module_evaluation",
      "data": {
        "narrative": "Varshini excelled in Module 5, successfully triaging the security incident as a SEV1 Critical event and maintaining exceptional, transparent communication under pressure. She patched the JWT auth middleware to properly handle whitespace-only and empty-token bypass vectors, verified all five test cases, and created a precise database restoration plan via Point-in-Time Recovery (PITR).",
        "overall": 4,
        "dimension_scores": [
          {
            "key": "hypothesis_quality",
            "score": 4,
            "observation": "Formulated specific, testable hypotheses regarding the Python strip() and partition() whitespace token parsing behavior.",
            "evidence": "Identified that whitespace-only authorization headers evaluate as truthy but produce empty tokens during parsing, bypassing standard presence checks."
          },
          {
            "key": "log_literacy",
            "score": 4,
            "observation": "Analyzed WAF log patterns efficiently, extracting key signals like empty auth headers and high-frequency HTTP 200 DELETE responses.",
            "evidence": "Extracted 47 unauthorized HTTP 200 deletions from unrecognized IP addresses, identifying a successful active exploit."
          },
          {
            "key": "reproduction_skill",
            "score": 4,
            "observation": "Reproduced the auth bypass securely with a crafted whitespace and empty Bearer request before applying any middleware fixes.",
            "evidence": "Verified that Authorization: ' ' bypassed presence checks and reached JWT validation in the middleware."
          },
          {
            "key": "communication_under_pressure",
            "score": 5,
            "observation": "THIS IS THE PRIMARY DIMENSION. Demonstrated exceptional transparency, structure, and timeliness under pressure, providing honest updates without downplaying severity.",
            "evidence": "Resisted pressure to downplay the breach, maintaining clear updates to the VP while explaining that redirect services remained unaffected to allow the sales demo to proceed."
          },
          {
            "key": "root_cause_depth",
            "score": 4,
            "observation": "Traced the vulnerability to differences in Python's falsy evaluation of empty strings vs truthy evaluation of whitespace, and empty JWT payload behavior.",
            "evidence": "Explained why presence check passes for ' ' but partition results in empty token, leading to a weak JWT validation bypass."
          },
          {
            "key": "postmortem_quality",
            "score": 4,
            "observation": "Formulated a structured Point-in-Time Recovery (PITR) plan and drafted blameless postmortem Slack updates to rebuild organizational trust.",
            "evidence": "Constructed a technical recovery plan to isolate the 12 deleted links across 8 accounts at 14:20 UTC and restore them to production without overwriting modern transactions."
          }
        ],
        "strengths": [
          "Varshini maintained perfect transparency under pressure, refusing to downplay a confirmed security incident despite heavy stakeholder anxiety.",
          "She formulated a precise, secure, and surgical Point-in-Time database recovery plan that avoided destructive overwrites of active transactions."
        ],
        "growth_areas": [],
        "recommendation": "In the next module, practice tracing logic flows across multiple services and message queues, as bugs will begin spanning system boundaries.",
        "public_evidence": [
          {
            "artifact": "app/auth.py & database restoration plan",
            "student_action": "Implemented a multi-layered defense-in-depth auth middleware check and formulated a PITR database recovery procedure.",
            "technical_detail": "Auth middleware validation using strict whitespace trimming, format checks (split), and SQL-level point-in-time state querying.",
            "proof": "All 51 integration tests passed successfully; PITR plan validated 12 links restored across 8 accounts.",
            "ability": "Incident response coordination, technical triage under pressure, and database point-in-time recovery execution.",
            "reviewer_value": "Demonstrates senior-level maturity in security response, stakeholder management, and data recovery safety.",
            "confidence": "demonstrated"
          }
        ],
        "student_knowledge": {
          "terminology_gaps": [],
          "concepts_demonstrated": [
            {
              "concept": "Incident Command and Communication",
              "evidence": "Established a structured 15-minute update loop and resisted stakeholder pressure to minimize breach reporting."
            },
            {
              "concept": "Point-in-Time Recovery (PITR)",
              "evidence": "Designed a surgical database restoration plan querying historical state at 14:20 UTC to recover only specific deleted rows."
            }
          ],
          "teaching_approaches": [
            {
              "concept": "Blameless Postmortem",
              "approach": "example",
              "detail": "Explained how blameless incident analysis focuses on systemic protocol improvements rather than individual blame, using aviation industry cockpit design safety analogies.",
              "effective": True
            }
          ],
          "effective_level": "intermediate",
          "learning_style_signals": [
            "applied_problem_solver",
            "hands_on_exploration"
          ],
          "confidence_level": "medium"
        }
      }
    }
  ]
}

with open("report_payload.json", "w") as f:
    json.dump(payload, f, indent=2)

print("Saved report_payload.json. Running upsk report...")
res = subprocess.run(["..\\upsk.exe", "report", "--file", "report_payload.json"], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
print("Exit code:", res.returncode)

