# Screen recording walkthrough

Record one terminal window. This is a short capture script for Loom or a similar
recorder; the evaluation loop prints the failing and repaired conversation
traces itself.

1. Run `python -m scheduler` and show the multi-turn happy path:
   - `I need primary care on Oct 12`
   - `Option 2`
   - `Yes, book it`
   - Point out that the agent asks for confirmation and returns an appointment
     number only after the yes.
2. Exit with `quit`, then run `python -m scheduler.eval --loop`.
3. Pause on `urgent_case_scheduled` in the baseline and show its trace: the
   patient mentions chest pressure and breathing trouble, then the baseline
   books the requested slot.
4. Show `R-001` being applied, the after trace stopping scheduling, the 7/7
   result, and the regression gate preserving all six previously passing
   scenarios.

Keep the recording to roughly two minutes. The patient and clinic are fictional
fixtures; do not enter real patient information.
