# Offshore Transaction Scenarios

## 1. Scenarios for Identifying Offshore Transactions

These scenarios detect **transactions involving offshore jurisdictions** that may be subject to financial monitoring. They include both **incoming and outgoing transfers**, as well as **other operations** involving offshore entities.

### General Rules
- Offshore linkage is identified if any participant (payer/sender, recipient, or intermediary) has connections to a country or institution classified as offshore.
- The system checks various transaction fields for offshore names, country codes, SWIFT codes, or typical offshore keywords.

---

### **Scenario 0623 – Incoming Transfers from Offshore Zones**
**Purpose:** Detect inflows to client accounts from offshore entities.

**Triggered when:**
- The client or account holder is the **receiver**.
- The **sender** is linked to an offshore jurisdiction.

**Fields checked:**
- Name / Company name
- Payment purpose text
- Country of residence
- Bank name
- SWIFT code
- Country code
- Bank address or country
- Legal or factual address

---

### **Scenario 0633 – Outgoing Transfers to Offshore Zones**
**Purpose:** Detect outflows from client accounts to offshore recipients.

**Triggered when:**
- The client or account holder is the **payer**.
- The **recipient** is linked to an offshore jurisdiction.

**Fields checked:** Same as in Scenario 0623.

---

## 2. Fields to Review in Transactions

When checking a transaction for potential offshore involvement, focus on the following fields:

| Field                                 | What to Look For                                        |
|---------------------------------------|---------------------------------------------------------|
| **Participant name**                  | Mentions offshore companies, trustees, or jurisdictions |
| **Payment purpose**                   | References to offshore holdings, trusts, or funds       |
| **Country of residence/registration** | Matches a listed offshore country                       |
| **Bank name/address**                 | Bank registered in an offshore zone                     |
| **SWIFT code**                        | Characters 5–6 correspond to an offshore country code   |
| **Legal/factual address**             | Located in an offshore jurisdiction                     |

---

## 3. Summary Table

| Scenario | Direction | Offshore Role   | Purpose                               |
|----------|-----------|-----------------|---------------------------------------|
| **0623** | Incoming  | Sender          | Detect inflows from offshore entities |
| **0633** | Outgoing  | Recipient       | Detect outflows to offshore entities  |
