# WNBA Prop Engine — Railway + Streamlit

Clean WNBA-only prop engine based on your MLB workflow.

## What it does

- Pulls **real WNBA lines only**
- Uses **Underdog first**
- Optional PrizePicks backup
- Shows **all WNBA player props**
- Builds projection, edge, EV, fair probability, Kelly, and signal
- Keeps **before / after snapshot saving**
- Keeps **grading + learning**
- Keeps **CLV tracking**
- Does not create fake lines

## Files

```text
app.py
requirements.txt
Procfile
runtime.txt
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Railway setup

1. Upload all files to GitHub.
2. Connect the GitHub repo to Railway.
3. Railway should detect the `Procfile`.
4. Deploy.

## Streamlit Cloud setup

1. Upload all files to GitHub.
2. Create new Streamlit app.
3. Main file path: `app.py`.

## Notes

The app will not show fake lines. If Underdog/PrizePicks return no WNBA board, the app will show a warning instead of inventing lines.

WNBA stat data uses the NBA/WNBA stats endpoint when available. If that endpoint blocks the host, the app still shows all real props but marks projections as lower confidence.
