# Glacial Risk Nepal

Glacial Lake Outburst Flood (GLOF) early warning system for Nepal using Sentinel-2 satellite imagery, U-Net segmentation, and anomaly detection.

## Project Structure

```
glacial-risk-nepal/
├── backend/          # Python FastAPI app
│   ├── main.py       # API entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # React app (Vite, deployed on Vercel)
│   ├── src/
│   ├── vercel.json
│   └── ...
├── package.json      # Root package.json (Vercel monorepo)
└── README.md
```

## Getting Started

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## License

MIT
