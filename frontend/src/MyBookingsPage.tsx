
import { useCallback, useEffect, useState } from "react";
import { useCustomerAuth } from "./CustomerAuthContext";
import "./MyBookingsPage.css";

const API = "http://127.0.0.1:8000";

type HistoryBooking = {
  booking_id: number;
  booking_reference: string;
  sport: string;
  booking_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  total_players: number;
  male_players: number;
  female_players: number;
  court_type: string;
  total_amount: number;
  status: string;
  payment_status: string;
};

export default function MyBookingsPage() {
  const { customer, customerToken, authLoading } = useCustomerAuth();

  const [bookings, setBookings] = useState<HistoryBooking[]>([]);
const [bookingQrs, setBookingQrs] = useState<Record<number, string>>({});
const [loading, setLoading] = useState(true);
const [error, setError] = useState("");

  const loadBookings = useCallback(async () => {
  if (!customerToken) {
    setLoading(false);
    return;
  }

  setLoading(true);
  setError("");
  setBookingQrs({});

  try {
    const response = await fetch(`${API}/api/customer/bookings`, {
      headers: {
        Authorization: `Bearer ${customerToken}`,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Unable to load bookings.");
    }

    const customerBookings: HistoryBooking[] = data.bookings || [];

    setBookings(customerBookings);

    // Retrieve QR codes for confirmed and paid bookings.
    const eligibleBookings = customerBookings.filter(
      (item) =>
        item.status.toLowerCase() === "confirmed" &&
        item.payment_status.toLowerCase() === "paid"
    );

    const qrResults = await Promise.all(
      eligibleBookings.map(async (item) => {
        try {
          const qrResponse = await fetch(
            `${API}/api/access/booking/${item.booking_id}/qr`,
            {
              headers: {
                Authorization: `Bearer ${customerToken}`,
              },
            }
          );

          if (!qrResponse.ok) {
            console.error(
              `Unable to load QR for booking ${item.booking_id}`
            );
            return null;
          }

          const qrData = await qrResponse.json();

          return {
            bookingId: item.booking_id,
            qrDataUrl: qrData.qr_data_url,
          };
        } catch (err) {
          console.error(
            `QR loading failed for booking ${item.booking_id}:`,
            err
          );
          return null;
        }
      })
    );

    const qrMap: Record<number, string> = {};

    qrResults.forEach((result) => {
      if (result) {
        qrMap[result.bookingId] = result.qrDataUrl;
      }
    });

    setBookingQrs(qrMap);

  } catch (err) {
    setError(
      err instanceof Error ? err.message : "Something went wrong."
    );
  } finally {
    setLoading(false);
  }
}, [customerToken]);

  useEffect(() => {
  if (!authLoading && !customer) {
    window.location.replace("/book?returnTo=%2Fmy-bookings");
    return;
  }

  if (!authLoading && customer) {
    void loadBookings();
  }
}, [authLoading, customer, loadBookings]);


  if (authLoading) {
    return <main className="my-bookings-page">Checking your account...</main>;
  }

  if (!customer) {
    return null;
    }

  return (
    <main className="my-bookings-page">
      <div className="my-bookings-container">
        <a href="/" className="my-bookings-back">← Back to Home</a>

        <header className="my-bookings-header">
          <div>
            <span className="my-bookings-eyebrow">YOUR ACCOUNT</span>
            <h1>My Bookings</h1>
            <p>
              Welcome back, {customer.full_name}. View your court booking
              history and payment details here.
            </p>
          </div>

          <button
            className="my-bookings-refresh"
            onClick={() => void loadBookings()}
            disabled={loading}
          >
            {loading ? "Loading..." : "↻ Refresh"}
          </button>
        </header>

        <section className="my-bookings-summary">
          <div>
            <span>Total Bookings</span>
            <strong>{bookings.length}</strong>
          </div>
          <div>
            <span>Confirmed</span>
            <strong>
              {bookings.filter(
                (b) => b.status.toLowerCase() === "confirmed"
              ).length}
            </strong>
          </div>
          <div>
            <span>Pending</span>
            <strong>
              {bookings.filter(
                (b) => b.status.toLowerCase() === "pending"
              ).length}
            </strong>
          </div>
        </section>

        <section className="my-bookings-list-section">
          <div className="my-bookings-list-heading">
            <h2>Booking History</h2>
            <span>{bookings.length} records</span>
          </div>

          {loading ? (
            <p className="my-bookings-info">Loading your bookings...</p>
          ) : error ? (
            <div className="my-bookings-empty">
              <p>{error}</p>
              <button onClick={() => void loadBookings()}>Try Again</button>
            </div>
          ) : bookings.length === 0 ? (
            <div className="my-bookings-empty">
              <span className="my-bookings-empty-icon">🏸</span>
              <h3>No bookings yet</h3>
              <p>Your court bookings will appear here after you make one.</p>
              <a href="/book" className="my-bookings-primary">
                Book Your First Slot
              </a>
            </div>
          ) : (
            <div className="my-bookings-list">
              {bookings.map((item) => (
                <article className="my-booking-card" key={item.booking_id}>
                  <div className="my-booking-top">
                    <div>
                      <span className="my-booking-sport">{item.sport}</span>
                      <h3>{item.booking_reference}</h3>
                    </div>

                    <span
                      className={`my-booking-status status-${item.status.toLowerCase()}`}
                    >
                      {item.status}
                    </span>
                  </div>

                  <div className="my-booking-details">
                    <div>
                      <span>Date</span>
                      <strong>{item.booking_date}</strong>
                    </div>
                    <div>
                      <span>Time</span>
                      <strong>{item.start_time} – {item.end_time}</strong>
                    </div>
                    <div>
                      <span>Duration</span>
                      <strong>{item.duration_minutes} minutes</strong>
                    </div>
                    <div>
                      <span>Players</span>
                      <strong>{item.total_players}</strong>
                    </div>
                    <div>
                      <span>Court Type</span>
                      <strong>{item.court_type.replace("_", " ")}</strong>
                    </div>
                    <div>
                      <span>Payment</span>
                      <strong>{item.payment_status}</strong>
                    </div>
                  </div>

                  <div className="my-booking-bottom">
                    <span>Total Amount</span>
                    <strong>
                      ₹{Number(item.total_amount).toLocaleString("en-IN", {
                        minimumFractionDigits: 2,
                      })}
                    </strong>
                  </div>
                  {bookingQrs[item.booking_id] && (
  <div className="my-booking-qr">
    <div>
      <h4>Entry QR Code</h4>
      <p>Show this QR code to arena staff when you arrive.</p>
    </div>

    <img
      src={bookingQrs[item.booking_id]}
      alt={`Entry QR for ${item.booking_reference}`}
    />

    <p className="my-booking-qr-note">
      Keep this QR code ready for arena entry.
    </p>
  </div>
)}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
