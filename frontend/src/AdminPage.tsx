
import { useEffect, useState } from "react";
import "./AdminPage.css";

const API_URL = "http://127.0.0.1:8000";

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

type Facility = {
  facility_name: string;
  opening_time: string;
  closing_time: string;
  operating_days: string[];
  is_booking_enabled: boolean;
  max_players_per_hour: number;
};

type Sport = {
  name: string;
  hourly_rate: number;
  is_active: boolean;
};

type AdminConfig = {
  facility: Facility;
  sports: Sport[];
};

type Booking = {
  id: number;
  booking_reference: string;
  customer_name: string;
  customer_phone: string;
  sport_id: number;
  booking_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  total_players: number;
  male_players: number;
  female_players: number;
  court_type: string;
  total_amount: number;
  status: "pending" | "confirmed" | "cancelled" | "completed";
  payment_status: "unpaid" | "paid" | "failed" | "refunded";
  created_at?: string | null;
  sport: string;
};

type BookingResponse = {
  items: Booking[];
  total: number;
  page: number;
  page_size: number;
};

type BookingFilters = {
  search: string;
  date: string;
  status: string;
  payment: string;
  sport: string;
};

type DashboardSummary = {
  total_bookings: number;
  pending_bookings: number;
  confirmed_bookings: number;
  verified_revenue: number;
};


export default function AdminPage() {
  const [adminKey, setAdminKey] = useState("");
  const [config, setConfig] = useState<AdminConfig | null>(null);

  const [loading, setLoading] = useState(false);
  const [savingFacility, setSavingFacility] = useState(false);
  const [savingSport, setSavingSport] = useState<string | null>(null);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [bookings, setBookings] = useState<Booking[]>([]);
  const [bookingTotal, setBookingTotal] = useState(0);
  const [bookingPage, setBookingPage] = useState(1);
  const [bookingPageSize] = useState(20);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState("");
  const [bookingSearchInput, setBookingSearchInput] = useState("");
  const [bookingFilters, setBookingFilters] = useState<BookingFilters>({
    search: "",
    date: "",
    status: "",
    payment: "",
    sport: "",
  });

  const [updatingBooking, setUpdatingBooking] = useState<string | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  async function loadSummary() {
  setSummaryLoading(true);

  try {
    const data = await apiRequest<DashboardSummary>(
      "/api/admin/bookings/summary"
    );
    setSummary(data);
  } catch (err) {
    setBookingError(
      err instanceof Error ? err.message : "Unable to load summary."
    );
  } finally {
    setSummaryLoading(false);
  }
}
  
  // Auto-refresh bookings and summary every 15 seconds
  useEffect(() => {
    if (!config || !adminKey.trim()) return;

    const refreshDashboard = () => {
      void loadBookings(bookingPage, bookingFilters);
      void loadSummary();
    };

    const intervalId = window.setInterval(refreshDashboard, 15_000);

    return () => window.clearInterval(intervalId);
  }, [config, adminKey, bookingPage, bookingFilters]);


  async function apiRequest<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Key": adminKey.trim(),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail;

      const errorMessage =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((item: { msg?: string }) => item.msg).join(", ")
            : `Request failed (${response.status})`;

      throw new Error(errorMessage);
    }

    return response.json() as Promise<T>;
  }

  async function loadSettings() {
    setLoading(true);
    setError("");
    setMessage("");

    try {
      const data = await apiRequest<AdminConfig>("/api/admin/config");
      setConfig(data);
      await loadBookings(1);
      await loadSummary();
      setMessage("Admin settings loaded successfully.");
    } catch (err) {
      setConfig(null);
      setError(
        err instanceof Error ? err.message : "Unable to load settings.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setConfig(null);
    setBookings([]);
    setBookingTotal(0);
    setBookingPage(1);
    setMessage("");
    setError("");
    setBookingError("");
  }, [adminKey]);

  function updateFacility<K extends keyof Facility>(
    key: K,
    value: Facility[K],
  ) {
    setConfig((current) =>
      current
        ? {
            ...current,
            facility: {
              ...current.facility,
              [key]: value,
            },
          }
        : current,
    );
  }

  function updateSport(name: string, changes: Partial<Sport>) {
    setConfig((current) =>
      current
        ? {
            ...current,
            sports: current.sports.map((sport) =>
              sport.name === name ? { ...sport, ...changes } : sport,
            ),
          }
        : current,
    );
  }

  async function saveFacility() {
    if (!config) return;

    setSavingFacility(true);
    setError("");
    setMessage("");

    try {
      const result = await apiRequest<{ message: string }>(
        "/api/admin/facility",
        {
          method: "PUT",
          body: JSON.stringify(config.facility),
        },
      );

      setMessage(result.message);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to save facility settings.",
      );
    } finally {
      setSavingFacility(false);
    }
  }

  async function saveSport(sport: Sport) {
    setSavingSport(sport.name);
    setError("");
    setMessage("");

    try {
      const result = await apiRequest<{ message: string }>(
        `/api/admin/sports/${encodeURIComponent(sport.name)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            hourly_rate: Number(sport.hourly_rate),
            is_active: sport.is_active,
          }),
        },
      );

      setMessage(`${sport.name}: ${result.message}`);
      await loadSettings();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to save sport pricing.",
      );
    } finally {
      setSavingSport(null);
    }
  }

  function toggleDay(day: string) {
    if (!config) return;

    const days = config.facility.operating_days;

    updateFacility(
      "operating_days",
      days.includes(day)
        ? days.filter((item) => item !== day)
        : WEEKDAYS.filter((item) => [...days, day].includes(item)),
    );
  }

  async function loadBookings(
    page = 1,
    filters: BookingFilters = bookingFilters,
  ) {
    setBookingLoading(true);
    setBookingError("");

    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(bookingPageSize),
      });

      if (filters.search.trim()) {
        params.set("search", filters.search.trim());
      }

      if (filters.date) params.set("booking_date", filters.date);
      if (filters.status) params.set("status", filters.status);
      if (filters.payment) params.set("payment_status", filters.payment);
      if (filters.sport) params.set("sport", filters.sport);

      const data = await apiRequest<BookingResponse>(
        `/api/admin/bookings?${params.toString()}`,
      );

      setBookings(data.items);
      setBookingTotal(data.total);
      setBookingPage(data.page);
    } catch (err) {
      setBookings([]);
      setBookingTotal(0);
      setBookingError(
        err instanceof Error ? err.message : "Unable to load bookings.",
      );
    } finally {
      setBookingLoading(false);
    }
  }

  function applyBookingFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const filters = {
      ...bookingFilters,
      search: bookingSearchInput,
    };

    setBookingFilters(filters);
    void loadBookings(1, filters);
  }

  async function updateBooking(
    booking: Booking,
    kind: "status" | "payment",
    value: string,
  ) {
    const currentValue =
      kind === "status" ? booking.status : booking.payment_status;

    if (value === currentValue) return;

    if (
      kind === "payment" &&
      value === "paid" &&
      !window.confirm(
        "Have you verified that this booking's payment was actually received?",
      )
    ) {
      return;
    }

    if (
      kind === "status" &&
      value === "cancelled" &&
      booking.payment_status === "paid" &&
      !window.confirm(
        "This booking is marked as paid. Your backend may reject cancellation until the payment/refund is handled. Continue?",
      )
    ) {
      return;
    }

    setUpdatingBooking(`${booking.booking_reference}-${kind}`);
    setBookingError("");
    setMessage("");

    try {
      
      const params = new URLSearchParams({
        [kind === "payment" ? "payment_status" : "status"]: value,
      });


      await apiRequest(
        `/api/admin/bookings/${encodeURIComponent(booking.booking_reference)}/${kind}?${params.toString()}`,
        { method: "PATCH" },
      );

      setMessage(
        kind === "status"
          ? "Booking status updated."
          : "Payment status updated.",
      );

      await loadBookings(bookingPage);
      await loadSummary();
    } catch (err) {
      setBookingError(
        err instanceof Error ? err.message : "Unable to update booking.",
      );
      await loadBookings(bookingPage);
    } finally {
      setUpdatingBooking(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(bookingTotal / bookingPageSize));

  return (
    <main className="admin-page">
      <header className="admin-header">
        <a className="admin-brand" href="/">
          <span className="admin-brand-mark">K</span>
          <span>
            THE KING
            <strong>ELITE ARENA</strong>
          </span>
        </a>

        <a className="admin-back-link" href="/">
          View website ↗
        </a>
      </header>

      <section className="admin-main">
        <div className="admin-title">
          <span className="admin-eyebrow">ARENA MANAGEMENT</span>
          <h1>
            Admin <span>Dashboard</span>
          </h1>
          <p>Manage bookings, payments, facility settings, and sports pricing.</p>
        </div>

        <section className="admin-panel admin-auth-panel">
          <div>
            <h2>Admin access</h2>
            <p>
              Enter the admin API key configured in your backend environment.
            </p>
          </div>

          <form
            className="admin-key-form"
            onSubmit={(event) => {
              event.preventDefault();
              void loadSettings();
            }}
          >
            <input
              type="password"
              autoComplete="current-password"
              aria-label="Admin API key"
              placeholder="Enter admin API key"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              required
            />

            <button type="submit" disabled={loading}>
              {loading ? "Connecting..." : "Load dashboard"}
            </button>
          </form>
        </section>

        {error && <div className="admin-alert admin-error">{error}</div>}

        {message && (
          <div className="admin-alert admin-success">{message}</div>
        )}

        {config && (
          <>
            {/* DASHBOARD SUMMARY CARDS */}
    <section className="admin-summary-grid" aria-label="Booking summary">
      <article className="admin-summary-card">
        <span>Total Bookings</span>
        <strong>
          {summaryLoading && !summary ? "..." : summary?.total_bookings ?? 0}
        </strong>
        <small>All recorded bookings</small>
      </article>

      <article className="admin-summary-card">
        <span>Pending Bookings</span>
        <strong>
          {summaryLoading && !summary ? "..." : summary?.pending_bookings ?? 0}
        </strong>
        <small>Awaiting confirmation</small>
      </article>

      <article className="admin-summary-card">
        <span>Confirmed Bookings</span>
        <strong>
          {summaryLoading && !summary ? "..." : summary?.confirmed_bookings ?? 0}
        </strong>
        <small>Confirmed reservations</small>
      </article>

      <article className="admin-summary-card">
        <span>Verified Revenue</span>
        <strong>
          {summaryLoading && !summary
            ? "..."
            : `₹${(summary?.verified_revenue ?? 0).toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`}
        </strong>
        <small>Bookings marked as paid</small>
      </article>
    </section>

            <section className="admin-panel">
              <div className="admin-section-heading">
                <div>
                  <span className="admin-eyebrow">RESERVATIONS</span>
                  <h2>Bookings Management</h2>
                  <p>Search bookings and manage their current status.</p>
                </div>

                <span className="admin-tag">
                  {bookingTotal} bookings
                </span>
              </div>

              <form
                className="admin-booking-filters"
                onSubmit={applyBookingFilters}
              >
                <input
                  placeholder="Search name, phone, or reference"
                  aria-label="Search bookings"
                  value={bookingSearchInput}
                  onChange={(event) =>
                    setBookingSearchInput(event.target.value)
                  }
                />

                <input
                  type="date"
                  aria-label="Booking date"
                  value={bookingFilters.date}
                  onChange={(event) =>
                    setBookingFilters((current) => ({
                      ...current,
                      date: event.target.value,
                    }))
                  }
                />

                <select
                  aria-label="Booking status filter"
                  value={bookingFilters.status}
                  onChange={(event) =>
                    setBookingFilters((current) => ({
                      ...current,
                      status: event.target.value,
                    }))
                  }
                >
                  <option value="">All booking statuses</option>
                  <option value="pending">Pending</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="completed">Completed</option>
                </select>

                <select
                  aria-label="Payment status filter"
                  value={bookingFilters.payment}
                  onChange={(event) =>
                    setBookingFilters((current) => ({
                      ...current,
                      payment: event.target.value,
                    }))
                  }
                >
                  <option value="">All payment statuses</option>
                  <option value="unpaid">Unpaid</option>
                  <option value="paid">Paid</option>
                  <option value="failed">Failed</option>
                  <option value="refunded">Refunded</option>
                </select>

                <select
                  aria-label="Sport filter"
                  value={bookingFilters.sport}
                  onChange={(event) =>
                    setBookingFilters((current) => ({
                      ...current,
                      sport: event.target.value,
                    }))
                  }
                >
                  <option value="">All sports</option>
                  <option value="Badminton">Badminton</option>
                  <option value="Pickleball">Pickleball</option>
                </select>

                <button type="submit" disabled={bookingLoading}>
                  Apply filters
                </button>
              </form>

              {bookingError && (
                <div className="admin-alert admin-error">{bookingError}</div>
              )}

              <div className="admin-booking-toolbar">
                <span>
                  {bookingLoading
                    ? "Loading bookings..."
                    : `${bookingTotal} matching bookings`}
                </span>

                <button
                  type="button"
                  className="admin-secondary-button"
                  onClick={() => void loadBookings(bookingPage)}
                  disabled={bookingLoading}
                >
                  Refresh
                </button>
              </div>

              <div className="admin-bookings-table-wrap">
                <table className="admin-bookings-table">
                  <thead>
                    <tr>
                      <th>Booking reference</th>
                      <th>Customer</th>
                      <th>Date & time</th>
                      <th>Sport</th>
                      <th>Players</th>
                      <th>Amount</th>
                      <th>Booking status</th>
                      <th>Payment status</th>
                    </tr>
                  </thead>

                  <tbody>
                    {bookings.map((booking) => (
                      <tr key={booking.booking_reference}>
                        <td>
                          <strong>{booking.booking_reference}</strong>
                          <small>{booking.court_type.replace("_", " ")}</small>
                        </td>

                        <td>
                          {booking.customer_name}
                          <small>{booking.customer_phone}</small>
                        </td>

                        <td>
                          {booking.booking_date}
                          <small>
                            {booking.start_time}–{booking.end_time}
                          </small>
                        </td>

                        <td>{booking.sport}</td>
                        <td>{booking.total_players}</td>
                        <td>₹{Number(booking.total_amount).toFixed(2)}</td>

                        <td>
                          <select
                            aria-label={`Booking status ${booking.booking_reference}`}
                            value={booking.status}
                            disabled={
                              updatingBooking ===
                              `${booking.booking_reference}-status`
                            }
                            onChange={(event) =>
                              void updateBooking(
                                booking,
                                "status",
                                event.target.value,
                              )
                            }
                          >
                            <option value="pending">Pending</option>
                            <option value="confirmed">Confirmed</option>
                            <option value="cancelled">Cancelled</option>
                            <option value="completed">Completed</option>
                          </select>
                        </td>

                        <td>
                          <select
                            aria-label={`Payment status ${booking.booking_reference}`}
                            value={booking.payment_status}
                            disabled={
                              updatingBooking ===
                              `${booking.booking_reference}-payment`
                            }
                            onChange={(event) =>
                              void updateBooking(
                                booking,
                                "payment",
                                event.target.value,
                              )
                            }
                          >
                            <option value="unpaid">Unpaid</option>
                            <option value="paid">Paid</option>
                            <option value="failed">Failed</option>
                            <option value="refunded">Refunded</option>
                          </select>
                        </td>
                      </tr>
                    ))}

                    {!bookings.length && !bookingLoading && (
                      <tr>
                        <td colSpan={8} className="admin-empty-state">
                          No bookings loaded. Click “Load bookings” to view
                          reservations.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="admin-pagination">
                <span>
                  Page {bookingPage} of {totalPages}
                </span>

                <div>
                  <button
                    type="button"
                    className="admin-secondary-button"
                    disabled={bookingLoading || bookingPage <= 1}
                    onClick={() => void loadBookings(bookingPage - 1)}
                  >
                    Previous
                  </button>

                  <button
                    type="button"
                    className="admin-secondary-button"
                    disabled={bookingLoading || bookingPage >= totalPages}
                    onClick={() => void loadBookings(bookingPage + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>

              <p className="admin-help">
                Payment status should only be marked as paid after verifying
                the actual payment. Online payment gateway integration is not
                enabled yet.
              </p>
            </section>

            <section className="admin-panel">
              <div className="admin-section-heading">
                <div>
                  <span className="admin-eyebrow">GENERAL</span>
                  <h2>Facility settings</h2>
                </div>
                <span className="admin-tag">Settings</span>
              </div>

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void saveFacility();
                }}
              >
                <div className="admin-form-grid">
                  <label className="admin-field admin-full-field">
                    Facility name
                    <input
                      value={config.facility.facility_name}
                      onChange={(event) =>
                        updateFacility("facility_name", event.target.value)
                      }
                      maxLength={150}
                      required
                    />
                  </label>

                  <label className="admin-field">
                    Opening time
                    <input
                      type="time"
                      value={config.facility.opening_time}
                      onChange={(event) =>
                        updateFacility("opening_time", event.target.value)
                      }
                      required
                    />
                  </label>

                  <label className="admin-field">
                    Closing time
                    <input
                      type="time"
                      value={config.facility.closing_time}
                      onChange={(event) =>
                        updateFacility("closing_time", event.target.value)
                      }
                      required
                    />
                  </label>

                  <label className="admin-field">
                    Maximum players at a time
                    <input
                      type="number"
                      min="1"
                      max="40"
                      value={config.facility.max_players_per_hour}
                      onChange={(event) =>
                        updateFacility(
                          "max_players_per_hour",
                          Number(event.target.value),
                        )
                      }
                      required
                    />
                  </label>
                </div>

                <div className="admin-days">
                  <span className="admin-field-title">Operating days</span>

                  <div className="admin-day-grid">
                    {WEEKDAYS.map((day) => (
                      <label className="admin-day" key={day}>
                        <input
                          type="checkbox"
                          checked={config.facility.operating_days.includes(day)}
                          onChange={() => toggleDay(day)}
                        />
                        <span>{day.slice(0, 3)}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <label className="admin-booking-toggle">
                  <span>
                    <strong>Accept bookings</strong>
                    <small>
                      Disable this to pause new customer bookings.
                    </small>
                  </span>

                  <input
                    type="checkbox"
                    checked={config.facility.is_booking_enabled}
                    onChange={(event) =>
                      updateFacility(
                        "is_booking_enabled",
                        event.target.checked,
                      )
                    }
                  />
                </label>

                <button
                  className="admin-primary-button"
                  type="submit"
                  disabled={savingFacility}
                >
                  {savingFacility ? "Saving..." : "Save facility settings"}
                </button>
              </form>
            </section>

            <section className="admin-panel">
              <div className="admin-section-heading">
                <div>
                  <span className="admin-eyebrow">RATES & AVAILABILITY</span>
                  <h2>Sports pricing</h2>
                </div>

                <span className="admin-tag">
                  {config.sports.length} sports
                </span>
              </div>

              <div className="admin-sports-list">
                {config.sports.map((sport) => (
                  <article className="admin-sport-card" key={sport.name}>
                    <div className="admin-sport-info">
                      <span className="admin-sport-icon">
                        {sport.name.toLowerCase() === "badminton" ? "🏸" : "🎾"}
                      </span>

                      <div>
                        <h3>{sport.name}</h3>
                        <span
                          className={
                            sport.is_active
                              ? "admin-status active"
                              : "admin-status inactive"
                          }
                        >
                          {sport.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    </div>

                    <div className="admin-sport-controls">
                      <label className="admin-field">
                        Hourly rate (₹)
                        <input
                          type="number"
                          min="0"
                          max="99999999"
                          step="0.01"
                          value={sport.hourly_rate}
                          onChange={(event) =>
                            updateSport(sport.name, {
                              hourly_rate: Number(event.target.value),
                            })
                          }
                          required
                        />
                      </label>

                      <label className="admin-active-toggle">
                        <input
                          type="checkbox"
                          checked={sport.is_active}
                          onChange={(event) =>
                            updateSport(sport.name, {
                              is_active: event.target.checked,
                            })
                          }
                        />
                        Active
                      </label>

                      <button
                        type="button"
                        className="admin-primary-button"
                        onClick={() => void saveSport(sport)}
                        disabled={savingSport !== null}
                      >
                        {savingSport === sport.name
                          ? "Saving..."
                          : "Save rate"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>

              <p className="admin-help">
                Deactivated sports are hidden from the public pricing API.
                Court allocation is not managed from this dashboard.
              </p>
            </section>
          </>
        )}
      </section>

      <footer className="admin-footer">
        The King Elite Arena · Admin tools
      </footer>
    </main>
  );
}
