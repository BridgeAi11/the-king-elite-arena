
import { useEffect, useState } from "react";
import "./BookingPage.css";

const API = "http://127.0.0.1:8000";

type Sport = {
  name: "Badminton" | "Pickleball";
  hourly_rate: number;
};

type Facility = {
  is_booking_enabled: boolean;
  opening_time: string;
  closing_time: string;
  max_players_per_hour: number;
};

export default function BookingPage() {
  const [sports, setSports] = useState<Sport[]>([]);
  const [facility, setFacility] = useState<Facility | null>(null);
  const [sport, setSport] = useState<"Badminton" | "Pickleball">("Badminton");
  const [bookingDate, setBookingDate] = useState("");
  const [startTime, setStartTime] = useState("07:00");
  const [duration, setDuration] = useState(60);
  const [malePlayers, setMalePlayers] = useState(0);
  const [femalePlayers, setFemalePlayers] = useState(1);
  const [courtType, setCourtType] = useState<"general" | "girls_only">("general");
  const [customerName, setCustomerName] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("");
  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(false);

 useEffect(() => {
  let cancelled = false;

  async function loadConfig() {
    try {
      const response = await fetch(`${API}/api/public/config`);

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      if (!cancelled) {
        setFacility(data.facility);
        setSports(data.sports);

        if (data.sports.length > 0) {
          setSport(data.sports[0].name);
        }
      }
    } catch (error) {
      if (!cancelled) {
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load facility settings."
        );
      }
    }
  }

  loadConfig();

  return () => {
    cancelled = true;
  };
}, []);

  const totalPlayers = malePlayers + femalePlayers;
  const selectedSport = sports.find((s) => s.name === sport);
  const estimatedAmount = selectedSport
    ? (selectedSport.hourly_rate * duration) / 60
    : 0;

  async function submitBooking(e: React.FormEvent) {
    e.preventDefault();
    setMessage("");
    setBooking(null);

    if (totalPlayers < 1) {
      setMessage("Add at least one player.");
      return;
    }

    if (courtType === "girls_only" && (malePlayers > 0 || femalePlayers < 1)) {
      setMessage("The girls-only court is exclusively for women players.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API}/api/bookings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: customerName,
          customer_phone: phone,
          sport,
          booking_date: bookingDate,
          start_time: `${startTime}:00`,
          duration_minutes: duration,
          total_players: totalPlayers,
          male_players: malePlayers,
          female_players: femalePlayers,
          court_type: courtType,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail ?? "Booking failed.")
        );
      }

      setBooking(data);
      setMessage(data.message);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Booking failed.");
    } finally {
      setLoading(false);
    }
  }

    if (!facility) {
    return (
        <main className="booking-page">
        <h2>{message ? "Unable to load booking page" : "Loading facility settings…"}</h2>
        {message && <p role="alert">{message}</p>}
        {message && (
            <button onClick={() => window.location.reload()}>
            Try again
            </button>
        )}
        </main>
    );
    }

  return (
    <main className="booking-page">
      <section className="booking-card">
        <p className="booking-eyebrow">THE KING ELITE ARENA</p>
        <h1>Book Your Play</h1>
        <p>Book individually and connect with other players at the arena.</p>

        {!facility.is_booking_enabled ? (
          <p>Online bookings are currently unavailable.</p>
        ) : (
          <form onSubmit={submitBooking}>
            <label>
              Full name
              <input required minLength={2} value={customerName}
                onChange={(e) => setCustomerName(e.target.value)} />
            </label>

            <label>
              Phone number
              <input required minLength={8} maxLength={20}
                value={phone} onChange={(e) => setPhone(e.target.value)} />
            </label>

            <label>
              Sport
              <select value={sport} onChange={(e) => {
                const next = e.target.value as "Badminton" | "Pickleball";
                setSport(next);
                if (next === "Pickleball") setCourtType("general");
              }}>
                {sports.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name} — ₹{s.hourly_rate}/hour
                  </option>
                ))}
              </select>
            </label>

            <label>
              Date
              <input type="date" required min={new Date().toLocaleDateString("en-CA")}
                value={bookingDate} onChange={(e) => setBookingDate(e.target.value)} />
            </label>

            <label>
              Start time
              <input type="time" required value={startTime}
                onChange={(e) => setStartTime(e.target.value)} />
            </label>

            <label>
              Duration
              <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                <option value={30}>30 minutes</option>
                <option value={60}>1 hour</option>
                <option value={90}>1 hour 30 minutes</option>
                <option value={120}>2 hours</option>
                <option value={180}>3 hours</option>
              </select>
            </label>

            <div className="player-grid">
              <label>
                Male players
                <input type="number" min={0} max={40} value={malePlayers}
                  onChange={(e) => setMalePlayers(Number(e.target.value))} />
              </label>
              <label>
                Female players
                <input type="number" min={0} max={40} value={femalePlayers}
                  onChange={(e) => setFemalePlayers(Number(e.target.value))} />
              </label>
            </div>

            <label>
              Court eligibility
              <select value={courtType} onChange={(e) =>
                setCourtType(e.target.value as "general" | "girls_only")}>
                <option value="general">General court — mixed groups allowed</option>
                {sport === "Badminton" && (
                  <option value="girls_only">Girls-only court — women players only</option>
                )}
              </select>
            </label>

            <div className="booking-summary">
              <p>Total players: <strong>{totalPlayers}</strong></p>
              <p>Estimated total: <strong>₹{estimatedAmount.toFixed(2)}</strong></p>
              <small>Payment integration is not enabled yet.</small>
            </div>

            <button type="submit" disabled={loading}>
              {loading ? "Submitting…" : "Create Booking"}
            </button>
          </form>
        )}

        {message && <p role="status" className="booking-message">{message}</p>}

        {booking && (
          <div className="booking-confirmation">
            <h2>Booking created!</h2>
            <p>Reference: <strong>{booking.booking_reference}</strong></p>
            <p>Date: {booking.booking_date}</p>
            <p>Time: {booking.start_time}–{booking.end_time}</p>
            <p>Amount: ₹{booking.total_amount}</p>
            <p>Status: {booking.status} · {booking.payment_status}</p>
          </div>
        )}
      </section>
    </main>
  );
}
