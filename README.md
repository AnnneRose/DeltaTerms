# DeltaTerms

install all packages in requirements.txt

## Local development without Vite

1. Install frontend dependencies:

```bash
npm install
```

2. Start the React app with webpack dev server:

```bash
npm run dev
```

This opens the frontend at `http://localhost:3000`.

3. Start the Flask backend in another terminal:

```bash
python app.py
```

Flask runs by default at `http://localhost:5000`.

4. If your React app calls backend APIs under `/api`, webpack dev server proxies those requests to Flask.

5. For production build:

```bash
npm run build
```
