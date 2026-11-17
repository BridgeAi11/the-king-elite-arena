
const API_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD
    ? "https://king-elite-arena-api.onrender.com"
    : "http://127.0.0.1:8000")
).replace(/\/+$/, "");

export default API_URL;
