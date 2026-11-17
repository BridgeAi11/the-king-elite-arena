
import { useEffect, useState } from "react";
import "./BookingPage.css";
import { useCustomerAuth } from "./CustomerAuthContext";
import API from "./api";

declare global {
  interface Window {
    Razorpay: new (options: {
      key: string;
      amount: number;
      currency: string;
      name: string;
      description: string;
      order_id: string;
      prefill: {
        name: string;
        contact: string;
      };
      handler: (response: {
        razorpay_payment_id: string;
        razorpay_order_id: string;
        razorpay_signature: string;
      }) => void;
      modal?: {
        ondismiss?: () => void;
      };
    }) => {
      open: () => void;
    };
  }
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }

    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);

    document.body.appendChild(script);
  });
}


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



type Booking = {
  booking_id: number;
  booking_reference: string;
  booking_date: string;
  start_time: string;
  end_time: string;
  total_amount: number;
  status: string;
  payment_status: string;
};





export default function BookingPage() {
   const returnToParam = new URLSearchParams(
    window.location.search
  ).get("returnTo");

  const returnTo =
    returnToParam === "/my-bookings" ||
    returnToParam === "/my-membership"
      ? returnToParam
      : null;

  const selectedMembershipPlanId = new URLSearchParams(
  window.location.search
).get("membershipPlan");
  console.log("Selected Membership Plan:", selectedMembershipPlanId);     
  const [sports, setSports] = useState<Sport[]>([]);
  const [facility, setFacility] = useState<Facility | null>(null);

  const [sport, setSport] = useState<"Badminton" | "Pickleball">("Badminton");
  const [bookingDate, setBookingDate] = useState("");
  const [startTime, setStartTime] = useState("07:00");
  const [duration, setDuration] = useState(60);

  const [malePlayers, setMalePlayers] = useState(0);
  const [femalePlayers, setFemalePlayers] = useState(1);

  const [courtType, setCourtType] = useState<"general" | "girls_only">(
    "general"
  );
  

  // Shared customer authentication
const {
  customer,
  customerToken,
  authLoading,
  loginCustomer,
  logoutCustomer,
} = useCustomerAuth();

useEffect(() => {
  if (!authLoading && customer && returnTo) {
    window.location.replace(returnTo);
  }
}, [authLoading, customer, returnTo]);

const [customerName, setCustomerName] = useState("");
const [phone, setPhone] = useState("");
const [otp, setOtp] = useState("");
const [otpSent, setOtpSent] = useState(false);
const [otpLoading, setOtpLoading] = useState(false);

  // Booking
  const [message, setMessage] = useState("");
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<"online" | "">("");
  // Booking QR
  const [bookingQr, setBookingQr] = useState<string | null>(null);

  
  const [couponCode, setCouponCode] = useState("");
  const [couponLoading, setCouponLoading] = useState(false);
  const [couponError, setCouponError] = useState("");
  const [couponPreview, setCouponPreview] = useState<{
    original_amount: number;
    discount_amount: number;
    final_amount: number;
    coupon_code: string;
  } | null>(null);

  // Load facility configuration
  useEffect(() => {
    let cancelled = false;

    async function loadConfig() {
      try {
        const startedAt = performance.now();

const response = await fetch(`${API}/api/public/config`);

console.log(
  "Config API loading time:",
  (performance.now() - startedAt).toFixed(2),
  "ms"
);

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

  // Request OTP
  async function requestOTP(e: React.FormEvent) {
    e.preventDefault();
    setMessage("");
    setOtp("");
    setOtpSent(false);

    if (customerName.trim().length < 2) {
      setMessage("Please enter your full name.");
      return;
    }

    setOtpLoading(true);

    try {
      const response = await fetch(
        `${API}/api/customer-auth/request-otp`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            full_name: customerName.trim(),
            phone: phone.trim(),
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to send OTP."
        );
      }

      setOtpSent(true);
      setMessage("OTP sent successfully! Please check your mobile SMS.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "OTP request failed."
      );
    } finally {
      setOtpLoading(false);
    }
  }

  // Verify OTP
  async function verifyOTP(e: React.FormEvent) {
    e.preventDefault();
    setMessage("");

    
  


    if (!/^[0-9]{6}$/.test(otp)) {
      setMessage("Please enter a valid 6-digit OTP.");
      return;
    }

    setOtpLoading(true);

    try {
      const response = await fetch(
        `${API}/api/customer-auth/verify-otp`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            phone: phone.trim(),
            otp,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "OTP verification failed."
        );
      }

      loginCustomer(data.access_token, data.customer);

      if (returnTo) {
        window.location.replace(returnTo);
        return;
      }

      setCustomerName(data.customer.full_name);
      setPhone(data.customer.phone);

      setOtp("");
      setOtpSent(false);
      setMessage("Login successful! You can now book your play.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "OTP verification failed."
      );
    } finally {
      setOtpLoading(false);
    }
  }




function clearCouponPreview() {
  setCouponPreview(null);
  setCouponError("");
  setPaymentMethod("");

}

async function applyCoupon() {
  if (!customerToken) {
    setCouponError("Please login first.");
    return;
  }

  if (!couponCode.trim()) {
    setCouponError("Enter a coupon code.");
    return;
  }

  setCouponLoading(true);
  setCouponError("");
  setCouponPreview(null);

  try {
    const response = await fetch(`${API}/api/coupons/validate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${customerToken}`,
      },
      body: JSON.stringify({
  code: couponCode.trim().toUpperCase(),
  applies_to: "booking",
  order_amount: estimatedAmount,
}),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Coupon validation failed."
      );
    }

    setCouponPreview({
      original_amount: Number(data.original_amount),
      discount_amount: Number(data.discount_amount),
      final_amount: Number(data.final_amount),
      coupon_code: data.coupon_code || couponCode.trim().toUpperCase(),
    });
  } catch (error) {
    setCouponError(
      error instanceof Error ? error.message : "Unable to validate coupon."
    );
  } finally {
    setCouponLoading(false);
  }
}

async function startRazorpayPayment(bookingId: number): Promise<void> {
  if (!customerToken || !customer) {
    throw new Error("Please login again to continue payment.");
  }

  const scriptLoaded = await loadRazorpayScript();

  if (!scriptLoaded) {
    throw new Error("Unable to load Razorpay. Please try again.");
  }

  // Create Razorpay order through backend
  const orderResponse = await fetch(
    `${API}/api/payments/create-order?booking_id=${bookingId}`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${customerToken}`,
      },
    }
  );

  const orderData = await orderResponse.json();

  if (!orderResponse.ok) {
    throw new Error(orderData.detail || "Unable to create payment order.");
  }

  // Open Razorpay Checkout
  await new Promise<void>((resolve, reject) => {
    const razorpay = new window.Razorpay({
      key: orderData.key_id,
      amount: orderData.amount,
      currency: orderData.currency,
      name: "The King Elite Arena",
      description: "Court Booking Payment",
      order_id: orderData.order_id,

      prefill: {
        name: customer.full_name,
        contact: customer.phone,
      },

      handler: async (paymentResponse) => {
        try {
          const verifyResponse = await fetch(`${API}/api/payments/verify`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${customerToken}`,
            },
            body: JSON.stringify(paymentResponse),
          });

          const verifyData = await verifyResponse.json();

          if (!verifyResponse.ok) {
            throw new Error(
              verifyData.detail || "Payment verification failed."
            );
          }

          resolve();
        } catch (error) {
          reject(error);
        }
      },

      modal: {
        ondismiss: () => {
          reject(new Error("Payment was cancelled."));
        },
      },
    });

    razorpay.open();
  });
}


// Generate and load booking QR after successful payment
async function loadBookingQr(bookingId: number): Promise<void> {
  if (!customerToken) {
    throw new Error("Please login again.");
  }

  const response = await fetch(
    `${API}/api/access/booking/${bookingId}/qr`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${customerToken}`,
      },
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || "Unable to generate booking QR."
    );
  }

  setBookingQr(data.qr_data_url);
}



  // Submit booking
  async function submitBooking(e: React.FormEvent) {
    e.preventDefault();

    setMessage("");
setBooking(null);
setBookingQr(null);

    if (!customer || !customerToken) {
      setMessage("Please login before creating a booking.");
      return;
    }

    const isFreeBooking = couponPreview?.final_amount === 0;

    if (!isFreeBooking && paymentMethod !== "online") {
      setMessage("Please select online payment to continue.");
      return;
    }

    if (totalPlayers < 1) {
      setMessage("Add at least one player.");
      return;
    }

    if (totalPlayers > facility!.max_players_per_hour) {
      setMessage(
        `Maximum ${facility!.max_players_per_hour} players are allowed per hour.`
      );
      return;
    }

    if (
      courtType === "girls_only" &&
      (malePlayers > 0 || femalePlayers < 1)
    ) {
      setMessage("The girls-only court is exclusively for women players.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API}/api/bookings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${customerToken}`,
        },
        body: JSON.stringify({
          sport,
          booking_date: bookingDate,
          start_time: `${startTime}:00`,
          duration_minutes: duration,
          total_players: totalPlayers,
          male_players: malePlayers,
          female_players: femalePlayers,
          court_type: courtType,
          coupon_code: couponPreview ? couponPreview.coupon_code : null,
          payment_method: isFreeBooking ? null : paymentMethod,
        }),
      });

      const data = await response.json();

      if (response.status === 401) {
        logoutCustomer();
        throw new Error("Your session expired. Please login again.");
      }

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail ?? "Booking failed.")
        );
      }

     setBooking(data);

if (isFreeBooking) {
  setMessage("Free booking confirmed successfully!");
  return;
}

if (!data.booking_id) {
  throw new Error(
    "Booking created, but booking ID is missing. Please contact the arena."
  );
}

setMessage("Booking created. Opening secure payment...");


await startRazorpayPayment(data.booking_id);

// Payment verification succeeded.
// Update booking confirmation.
const confirmedBooking = {
  ...data,
  status: "confirmed",
  payment_status: "paid",
};

setBooking(confirmedBooking);

setMessage("Payment successful! Your booking is confirmed.");

// Generate QR only after payment verification.
try {
  await loadBookingQr(data.booking_id);
} catch (qrError) {
  console.error("Booking QR error:", qrError);

  setMessage(
    "Payment successful! Booking confirmed, but QR could not be loaded. Please open My Bookings."
  );
}




    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Booking failed."
      );
    } finally {
      setLoading(false);
    }
  }

  // Loading facility settings
  if (!facility) {
    return (
      <main className="booking-page">
        <h2>
          {message
            ? "Unable to load booking page"
            : "Loading facility settings…"}
        </h2>

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
      <section
  className={`booking-card ${
    customer ? "booking-card-dashboard" : ""
  }`}
>
        <p className="booking-eyebrow">THE KING ELITE ARENA</p>

        <div className="booking-title-row">
  <h1>Book Your Play</h1>

  <a href="/" className="booking-home-link">
    ✕ Close
  </a>
</div>

        <p>
          Book individually and connect with other players at the arena.
        </p>

        {!facility.is_booking_enabled ? (
          <p>Online bookings are currently unavailable.</p>
        ) : authLoading ? (
          <p>Checking your customer session…</p>
        ) : !customer ? (
          <>
            <h2>Customer Login</h2>

            <p>Verify your mobile number to continue booking.</p>

            {!otpSent ? (
              <form onSubmit={requestOTP}>
                <label>
                  Full name
                  <input
                    type="text"
                    required
                    minLength={2}
                    maxLength={120}
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Enter your full name"
                  />
                </label>

                <label>
                  Phone number
                  <input
                    type="tel"
                    required
                    maxLength={20}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Enter your mobile number"
                  />
                </label>

                <button type="submit" disabled={otpLoading}>
                  {otpLoading ? "Sending OTP…" : "Send OTP"}
                </button>
              </form>
            ) : (
              <form onSubmit={verifyOTP}>
               <p>OTP sent to mobile number {phone}. Enter the 6-digit code.</p>

                <label>
                  Enter 6-digit OTP
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    value={otp}
                    onChange={(e) =>
                      setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))
                    }
                    placeholder="Enter OTP"
                  />
                </label>

                <button type="submit" disabled={otpLoading}>
                  {otpLoading ? "Verifying…" : "Verify OTP"}
                </button>

                <button
                  type="button"
                  disabled={otpLoading}
                  onClick={() => {
                    setOtpSent(false);
                    setOtp("");
                    setMessage("");
                  }}
                >
                  Change phone number
                </button>
              </form>
            )}
          </>
        ) : (
          <>
            <div className="customer-session">
  <div className="customer-session-avatar">
    {customer.full_name.charAt(0).toUpperCase()}
  </div>

  <div className="customer-session-info">
    <span className="customer-session-label">BOOKING AS</span>
    <strong>{customer.full_name}</strong>
    <span>{customer.phone}</span>
  </div>

  <span className="customer-session-badge">
    Logged In
  </span>
</div>
           
            <h2>Booking Details</h2>

            <form onSubmit={submitBooking} className="booking-form-grid">
              <div className="booking-fields-grid">

              <label>
                Sport
                <select
                  value={sport}
                  onChange={(e) => {
                    const next = e.target.value as
                      | "Badminton"
                      | "Pickleball";

                    setSport(next);
                      clearCouponPreview();

                      if (next === "Pickleball") {
                        setCourtType("general");
                      }
                  }}
                >
                  {sports.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name} — ₹{s.hourly_rate}/hour
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Date
                <input
                  type="date"
                  required
                  min={new Date().toLocaleDateString("en-CA")}
                  value={bookingDate}
                  onChange={(e) => setBookingDate(e.target.value)}
                />
              </label>

              <label>
                Start time
                <input
                  type="time"
                  required
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                />
              </label>

              <label>
                Duration
                <select
                  value={duration}
                  onChange={(e) => {
  setDuration(Number(e.target.value));
  clearCouponPreview();
}}
                >
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
                  <input
                    type="number"
                    min={0}
                    max={40}
                    value={malePlayers}
                    onChange={(e) =>
                      setMalePlayers(Number(e.target.value))
                    }
                  />
                </label>

                <label>
                  Female players
                  <input
                    type="number"
                    min={0}
                    max={40}
                    value={femalePlayers}
                    onChange={(e) =>
                      setFemalePlayers(Number(e.target.value))
                    }
                  />
                </label>
              </div>

              <label>
                Court eligibility
                <select
                  value={courtType}
                  onChange={(e) =>
                    setCourtType(
                      e.target.value as "general" | "girls_only"
                    )
                  }
                >
                  <option value="general">
                    General court — mixed groups allowed
                  </option>

                  {sport === "Badminton" && (
                    <option value="girls_only">
                      Girls-only court — women players only
                    </option>
                  )}
                </select>
              </label>
</div>
              <div className="booking-summary">
  <p>
    Total players: <strong>{totalPlayers}</strong>
  </p>

  <p>
    Original amount:{" "}
    <strong>₹{estimatedAmount.toFixed(2)}</strong>
  </p>

  <div className="coupon-section">
    <label>
      Coupon code
      <input
        type="text"
        value={couponCode}
        onChange={(e) => {
          setCouponCode(e.target.value.toUpperCase());
          setCouponPreview(null);
          setCouponError("");
        }}
        placeholder="Enter coupon code"
      />
    </label>

    <button
      type="button"
      onClick={applyCoupon}
      disabled={couponLoading || !couponCode.trim()}
    >
      {couponLoading ? "Checking..." : "Apply Coupon"}
    </button>

    {couponError && (
      <p className="coupon-error" role="alert">
        {couponError}
      </p>
    )}

    {couponPreview && (
      <div className="coupon-success">
        <p>Coupon applied: {couponPreview.coupon_code}</p>
        <p>
          Discount: ₹{couponPreview.discount_amount.toFixed(2)}
        </p>
      </div>
    )}
  </div>

  <p>
    Final amount:{" "}
    <strong>
      ₹
      {(couponPreview?.final_amount ?? estimatedAmount).toFixed(2)}
    </strong>
  </p>

  <small>
    {couponPreview?.final_amount !== 0 && (
  <div className="payment-method-section">
    <h3>Payment Method</h3>

    <label className="payment-option">
      <input
        type="radio"
        name="paymentMethod"
        value="online"
        checked={paymentMethod === "online"}
        onChange={() => setPaymentMethod("online")}
        required
      />

      <span>
        <strong>UPI / Online Payment</strong>
        <small>Pay online to confirm your booking.</small>
      </span>
    </label>
  </div>
)}
  </small>
</div>

              <button type="submit" disabled={loading}>
                {loading ? "Submitting…" : "Create Booking"}
              </button>
            </form>
          </>
        )}

        {message && (
          <p role="status" className="booking-message">
            {message}
          </p>
        )}

        {booking && (
          <div className="booking-confirmation">
            <h2>Booking created!</h2>

            <p>
              Reference: <strong>{booking.booking_reference}</strong>
            </p>

            <p>Date: {booking.booking_date}</p>

            <p>
              Time: {booking.start_time}–{booking.end_time}
            </p>

            <p>Amount: ₹{booking.total_amount}</p>

            <p>
              Status: {booking.status} · {booking.payment_status}
            </p>
          </div>
        )}

{bookingQr && (
  <div className="booking-qr-section">

    <h3>Your Entry QR Code</h3>

    <p>
      Your booking is confirmed!
      Show this QR code to arena staff when you arrive.
    </p>

    <img
      src={bookingQr}
      alt="Booking Entry QR Code"
      className="booking-qr-image"
    />

    <p className="booking-qr-note">
      Keep this QR code ready for arena entry.
    </p>

  </div>
)}

      </section>
    </main>
  );
}



