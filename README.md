# Fyers F&O Live Dashboard

Ek hi Streamlit dashboard mein: Option Chain (Call/Put), OI, OI % change,
Volume, Bid/Ask, PCR, OI Support/Resistance, OI Crossover (Call OI vs Put OI),
7 MA / 20 MA crossover, aur VWAP — sab live, Fyers API se.

## 1. Fyers API App banayein (ek baar ka kaam)

1. https://myapi.fyers.in/ par login karein (apne Fyers trading account se).
2. **"Create App"** par click karein.
3. Form bharein:
   - **App Name**: kuch bhi, jaise `MyDashboard`
   - **Redirect URL**: koi bhi valid URL daal sakte hain (jaise `https://www.google.com`
     ya apna GitHub Pages URL) — bas isse yaad rakhein, token generate karte waqt
     yahi exact URL use hoga.
   - Permissions me **Data + Order** dono select karein.
4. App create hone ke baad aapko milega:
   - **App ID** (jaise `ABC123XYZ-100`)
   - **Secret ID / Secret Key**
   Dono safe jagah save karein — kisi ke saath share na karein.

## 2. Daily Access Token generate karna

Fyers ka access token **roz expire hota hai** (raat ko reset). Isliye:

1. `generate_token.py` file kholein, apna `CLIENT_ID`, `SECRET_KEY`, `REDIRECT_URI` bharein.
2. Terminal me: `python generate_token.py`
3. Print hua URL browser me kholein → Fyers login → approve karein.
4. Redirect hone ke baad URL me `auth_code=...` milega — wo copy karke terminal me paste karein.
5. Script aapko `access_token` degi. Ye copy kar lein.

Is process ko roz subah market khulne se pehle repeat karna hoga (2 minute ka kaam).
Chahen to isse bhi automate kar sakte hain (Fyers ka TOTP-based auto-login flow),
lekin wo agla step hai — pehle isse manually chalayein.

## 3. GitHub par push karna

```bash
git init
git add .
git commit -m "Fyers live F&O dashboard"
git branch -M main
git remote add origin https://github.com/<aapka-username>/fyers-dashboard.git
git push -u origin main
```

**IMPORTANT:** `secrets.toml` ko kabhi commit na karein — `.gitignore` me already add hai.
Sirf `secrets.toml.example` GitHub par jayega (template ke liye).

## 4. Streamlit Community Cloud par deploy karna (free)

1. https://share.streamlit.io par GitHub se login karein.
2. **"New app"** → apna `fyers-dashboard` repo select karein → main file: `app.py`.
3. Deploy hone se pehle **"Advanced settings" → Secrets** me ye daalein:
   ```toml
   FYERS_CLIENT_ID = "ABC123XYZ-100"
   FYERS_ACCESS_TOKEN = "aaj_ka_access_token_yahan"
   ```
4. Deploy karein. App ka URL kahin se bhi (phone/laptop) khul jayega.
5. Roz naya access token generate karke **App → Settings → Secrets** me update
   karna hoga (ya dashboard ke sidebar me directly paste kar sakte hain — sidebar
   wala token sirf us session ke liye kaam karega).

## 5. Dashboard mein kya milega

- **Symbol** sidebar me daalein: `NSE:RELIANCE-EQ`, `NSE:TCS-EQ` etc. (koi bhi F&O stock)
- **Option Chain table**: LTP, Bid, Ask, Volume, OI, OI Change, OI Change %
- **PCR** (Put OI / Call OI)
- **OI Support** = sabse zyada Put OI wala strike
- **OI Resistance** = sabse zyada Call OI wala strike
- **OI Crossover** = Total Call OI aur Total Put OI ka live line chart + jab ek
  dusre ko cross kare to signal
- **7 MA / 20 MA crossover** = underlying price par (Golden Cross / Death Cross)
- **VWAP** = aaj ke intraday candles se

Auto-refresh interval sidebar se adjust kar sakte hain.

## Limitations / important notes

- Fyers ke daily API call limits hain — bahut chhota refresh interval (jaise 5s)
  rate-limit hit kar sakta hai. 30s+ recommended hai.
- Ye dashboard sirf ek F&O stock ka option chain ek time par dikhata hai
  (dropdown se symbol change karke doosra dekh sakte hain).
- Ye educational/analysis tool hai, trading/investment advice nahi hai.
