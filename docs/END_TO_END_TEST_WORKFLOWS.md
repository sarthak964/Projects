# TruStay: test all three roles through the browser

The modern demo workflows are now exposed at http://127.0.0.1:5173/.
Use the startup/login instructions in DEMO_USER_GUIDE.md. Existing sample accounts
are enough; creating a new identity is optional. Record job IDs so you can switch
roles and reopen the same job. Use fresh jobs to get fresh deadlines. No reset is
needed. AI/address providers can incur actual charges even though money is simulated.

## A. Happy path, from scratch

1. Log in as Renter (9000000001). Click New inspection.
2. Enter Connaught Place, New Delhi, India. Keep the walls/taps checklist or edit it.
   Create inspection and write down the job ID.
3. Log out. Log in as Reviewer (9000000002). New reviewer accounts first save a
   nearby location in My location & profile; the sample reviewer already has one.
4. Open Nearby jobs. Find the recorded ID, read address/estimate, Accept inspection
   and confirm. The final price is calculated at this point.
5. On the inspection detail, Mark visited and confirm.
6. Select the walls checklist item, choose your walls image, Upload photo. Repeat
   for taps. Check both originals appear under Evidence gallery.
7. Write specific findings for every item. For example: “Walls were inspected for
   cracks and damp patches; none were observed. Taps were checked for water flow
   and leaks; flow was steady and no leakage was observed.” Use honest demo findings.
8. Submit report and confirm. Then Assess report notes and confirm the provider call.
9. Check the actual outcome. Missing coverage means correct notes/photos and
   resubmit; provider failure leaves assessment retryable. Verified permits renter review.
10. Log out and log in as Renter. Open the same job, read notes/score and view photos.
11. Approve photos and confirm. Expect Paid, payment Released, review Approved.
12. Choose a score/comment under Your inspection rating, Submit rating and confirm.
    Reload; the saved rating replaces the form.
13. Reviewer: inspect Payment history. Admin: inspect Platform ledger and look up
    the job ID in Admin tools. Escrow should be zero after settlement; payout and
    commission should explain the released price. No bank transfer happens.

## B. Selected evidence rejection and AI-supported outcome

1. Create another job and repeat A through verification; do not approve photos.
2. As Renter, select disputed checklist items under Question the evidence, give a
   reason and Get photo-check fee quote. Changing items invalidates the old quote.
3. Review the amount and photo count, tick the fee agreement, then Confirm rejection
   and analyze. Confirm the provider call. Only the selected images are analyzed.
4. Read the actual result, not an assumed result. If AI supports the evidence,
   choose Accept AI result to settle with the check fee kept, OR continue C.
5. If the result requests replacements, continue D. Ambiguous/other outcomes may
   send the case directly to human review; follow the current saved stage.
6. Invalid/failing provider responses should show an error without a partial fee hold.

## C. Human review and losing-side appeal

1. From an AI-supported result, enter Reason for disagreeing, agree to the additional
   simulated ₹75 fee, Dispute AI result and confirm.
2. Admin: Human reviews, open the job. Compare photos, notes, concerns, AI observations
   and financial context. Select genuine/not genuine, Explain your decision,
   Review decision, then confirm. Verify saved notes and settlement status.
3. Genuine pays the reviewer; not genuine refunds applicable simulated amounts and
   affects reviewer standing according to backend rules. Check the actual ledger.
4. Log in as the losing participant. On the job, inspect Human decision & appeal,
   enter a reason before the displayed deadline, File appeal and confirm.
5. Admin: Appeals, open the job. Select uphold/overturn, save a reason and confirm.
   Check the resulting case, ledger and reviewer strikes. Overturn reverses relevant
   earlier entries and applies the new result; it does not erase accounting history.
6. Attempt to revisit the form; an already decided/ineligible appeal must not offer
   another submission. Test upheld and overturned outcomes on different cases.

## D. Replacement photos and renter recheck

1. Start from a job whose saved photo-review stage is awaiting_reupload. AI outcomes
   are not guaranteed for arbitrary photos; a fresh seeded job 7 also illustrates
   this branch if its deadlines have not elapsed.
2. Reviewer: open job; see rejected items and replacement deadline. Upload new photos
   for every rejected item. Originals do not count as replacements.
3. Confirm the gallery labels Original versus Reupload. Complete reupload and confirm.
4. Renter: compare rounds. Approve replacements and confirm: check Paid and the
   photo-check fee refund. On a separate case, give a reason and Request human
   decision instead: expect awaiting_human, then follow C from the admin decision.
5. A completed replacement round must not remain editable. Draft photo deletion
   requires confirmation; submitted originals remain protected.

## E. Other screens and safeguards

- Reviewer profile: save a nearby address, refresh, verify the location persists.
  Review rating/completed jobs/strikes/suspension. Try each distance filter.
- Admin Reviewer standing: inspect suspension records. Unsuspension needs a reason
  and confirmation; test only a deliberately suspended demo account.
- Admin tools: inspect scheduler status, look up a job ledger. Run the deadline sweep
  only when intentionally testing overdue cases: it can update several records.
- Notifications: inspect event links, mark unread events read, verify badge updates.
- Renter Support: optionally enter an owned job ID, ask a question, read reply/ticket
  ID. This is an explicit provider call; a ticket is a local record, not live-agent delivery.
- Wrong role/account: another renter cannot operate your inspection; another reviewer
  cannot submit evidence for your assignment. Role selection on login does not alter
  an existing account's role. Backend permissions remain authoritative.
- Validation: blank/duplicate checklist items, unsupported/over-8MiB images, missing
  item evidence and short notes should be rejected or clearly prevent submission.
- Mobile: navigate all role links horizontally, open forms/dialogs and evidence.
- Logout/refresh: same-tab refresh restores session, logout removes it, expired
  authorization returns to login. No tokens appear in photo URLs.

## F. Feedback to record

For each finding: role, job ID, screen/action, expected result, actual result,
visible error and screenshot. Share no tokens or provider keys. Describe color,
spacing, wording or interaction preferences after checking the workflow.

For historical API contracts see API_REFERENCE.md and http://127.0.0.1:8001/docs.
Legacy 30-day disputes remain available for eligible older jobs; they are not the
modern photo-review flow. Database resets/migrations remain CLI maintenance.


## Completed remaining controls

Renter and admin navigation now includes **30-day disputes**: browse cases, file an eligible older-job case, request AI triage, read recommendations and resolve escalated cases as admin. Modern jobs remain in their photo-review workflow. Notifications now have paging, unread filtering, refresh and Mark all read. Admin inspection details link directly to pending human reviews and appeals. These screens supersede earlier statements that legacy disputes were API-only. Database repair/backfill and migrations remain maintenance operations.
