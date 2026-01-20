# TensorGuardFlow QA Manual Checklist

**Version:** 2.3.0
**Date:** _____________
**Tester:** _____________

## Instructions
- Complete each item by marking PASS/FAIL
- Add notes for any failures or observations
- Screenshots should be saved to `artifacts/qa/screenshots/`

---

## 1. Login UX

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 1.1 | Navigate to login page | Login form displays | [ ] PASS [ ] FAIL | |
| 1.2 | Submit empty credentials | Error message shown | [ ] PASS [ ] FAIL | |
| 1.3 | Submit invalid email format | Validation error | [ ] PASS [ ] FAIL | |
| 1.4 | Submit wrong password | "Invalid credentials" error | [ ] PASS [ ] FAIL | |
| 1.5 | Submit valid credentials | Redirect to dashboard | [ ] PASS [ ] FAIL | |
| 1.6 | Loading state visible during login | Spinner/loading indicator shown | [ ] PASS [ ] FAIL | |
| 1.7 | Error messages are clear and actionable | No technical jargon | [ ] PASS [ ] FAIL | |

## 2. Dashboard Empty States

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 2.1 | Fresh org - no fleets | "0 Active Fleets" shown | [ ] PASS [ ] FAIL | |
| 2.2 | Fresh org - no telemetry | Empty state message | [ ] PASS [ ] FAIL | |
| 2.3 | Pipeline graph empty | Placeholder or instructions | [ ] PASS [ ] FAIL | |
| 2.4 | Stats show reasonable defaults | No NaN, undefined, or errors | [ ] PASS [ ] FAIL | |

## 3. Fleet Create/Rotate UX

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 3.1 | Create fleet button visible | Button clearly labeled | [ ] PASS [ ] FAIL | |
| 3.2 | Create fleet form validation | Name required | [ ] PASS [ ] FAIL | |
| 3.3 | Fleet created successfully | Success message, API key shown | [ ] PASS [ ] FAIL | |
| 3.4 | API key shown only once | Warning about single display | [ ] PASS [ ] FAIL | |
| 3.5 | Copy API key works | Copied to clipboard | [ ] PASS [ ] FAIL | |
| 3.6 | Rotate key button visible | Located in fleet details | [ ] PASS [ ] FAIL | |
| 3.7 | Rotate key confirmation | Confirmation dialog shown | [ ] PASS [ ] FAIL | |
| 3.8 | New key displayed after rotation | Key is different | [ ] PASS [ ] FAIL | |

## 4. Telemetry Ingest Visibility

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 4.1 | Ingest data via API | No errors | [ ] PASS [ ] FAIL | |
| 4.2 | Dashboard reflects new data | Stats updated within 30s | [ ] PASS [ ] FAIL | |
| 4.3 | Pipeline graph shows flow | Nodes visible | [ ] PASS [ ] FAIL | |
| 4.4 | Device count increments | New device counted | [ ] PASS [ ] FAIL | |

## 5. Error Message Clarity

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 5.1 | 401 error message | "Please login" or similar | [ ] PASS [ ] FAIL | |
| 5.2 | 403 error message | "Access denied" | [ ] PASS [ ] FAIL | |
| 5.3 | 404 error message | "Not found" | [ ] PASS [ ] FAIL | |
| 5.4 | 500 error message | Generic error, no stack trace | [ ] PASS [ ] FAIL | |
| 5.5 | Network error handling | "Connection failed" | [ ] PASS [ ] FAIL | |
| 5.6 | No sensitive info in errors | No paths, secrets, SQL | [ ] PASS [ ] FAIL | |

## 6. Responsive Layout

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 6.1 | Desktop (1920x1080) | Full layout, no overflow | [ ] PASS [ ] FAIL | |
| 6.2 | Laptop (1366x768) | Usable, all controls visible | [ ] PASS [ ] FAIL | |
| 6.3 | Tablet landscape (1024x768) | Sidebar collapses | [ ] PASS [ ] FAIL | |
| 6.4 | Browser zoom 150% | Remains usable | [ ] PASS [ ] FAIL | |

## 7. Navigation

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 7.1 | All sidebar links work | No 404 pages | [ ] PASS [ ] FAIL | |
| 7.2 | Back button works | Returns to previous page | [ ] PASS [ ] FAIL | |
| 7.3 | Deep link works | Direct URL loads correctly | [ ] PASS [ ] FAIL | |
| 7.4 | Logout clears session | Returns to login | [ ] PASS [ ] FAIL | |
| 7.5 | Protected pages redirect | Unauthenticated -> login | [ ] PASS [ ] FAIL | |

## 8. Copy Key Once Behavior

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 8.1 | New fleet shows API key | Key visible immediately | [ ] PASS [ ] FAIL | |
| 8.2 | Warning about one-time display | Clear warning message | [ ] PASS [ ] FAIL | |
| 8.3 | Key not shown on page refresh | Key no longer visible | [ ] PASS [ ] FAIL | |
| 8.4 | Key not retrievable later | No "show key" option | [ ] PASS [ ] FAIL | |

## 9. Security UX

| # | Test Case | Expected Result | Status | Notes |
|---|-----------|-----------------|--------|-------|
| 9.1 | Session timeout behavior | Re-login required | [ ] PASS [ ] FAIL | |
| 9.2 | Concurrent session handling | Works correctly | [ ] PASS [ ] FAIL | |
| 9.3 | Password field masked | Dots/asterisks shown | [ ] PASS [ ] FAIL | |

---

## Summary

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Login UX | 7 | | |
| Dashboard Empty States | 4 | | |
| Fleet Create/Rotate | 8 | | |
| Telemetry Visibility | 4 | | |
| Error Messages | 6 | | |
| Responsive Layout | 4 | | |
| Navigation | 5 | | |
| Copy Key Behavior | 4 | | |
| Security UX | 3 | | |
| **TOTAL** | **45** | | |

## Overall Result

[ ] **PASS** - All critical items passed
[ ] **FAIL** - Critical items failed (list below)

### Critical Failures:
1. _____________
2. _____________

### Notes/Observations:
_____________________________________________

---

**Signed off by:** _______________
**Date:** _______________
