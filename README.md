# WNBA Prop Engine — Streamlit Fixed

This is the safer Streamlit/Railway version.

## Fixes

- Loads the Streamlit page first instead of hanging on WNBA stats calls
- Uses shorter request timeouts
- Uses stable NumPy version for Streamlit Cloud
- Corrects WNBA scoreboard date formatting
- Keeps real lines only
- Keeps full player cards
- Keeps before/after save snapshots
- Keeps grading, learning, CLV

## Files

- app.py
- requirements.txt
- Procfile
- runtime.txt
- README.md

## Streamlit Cloud

Main file path:

```text
app.py
```

## Railway

Railway uses the included `Procfile`.

## Notes

If Underdog/PrizePicks do not return WNBA props, the app will load but show a warning. It will not invent fake lines.


## v2.2 Fix

- Fixed `TypeError: 'function' object is not iterable` caused by the Source request log display block.
