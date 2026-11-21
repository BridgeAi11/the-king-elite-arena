
import { useCallback, useEffect, useState } from "react";
import { useCustomerAuth } from "./CustomerAuthContext";
import "./MyMembershipPage.css";

import API_URL from "./api";


declare global {
  interface Window {
    Razorpay: new (options: {
      key: string;
      amount: number;
      currency: string;
      name: string;
      description: string;
      order_id: string;
      prefill: { name: string; contact: string };
      handler: (response: {
        razorpay_payment_id: string;
        razorpay_order_id: string;
        razorpay_signature: string;
      }) => void;
      modal?: { ondismiss?: () => void };
    }) => { open: () => void };
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


type Membership = {
  membership_id: number;
  plan_name: string;
  amount_paid: number;
  total_hours: number;
  used_hours: number;
  reserved_hours: number;
  remaining_hours: number;
  start_date: string;
  expiry_date: string;
  status: string;
};

type MembershipPlan = {
  id: number;
  name: string;
  description: string;
  price: number;
  validity_days: number;
  included_hours: number;
};

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function MyMembershipPage() {
  const { customer, customerToken, authLoading } = useCustomerAuth();

  const [memberships, setMemberships] = useState<Membership[]>([]);
const [membershipQrs, setMembershipQrs] = useState<Record<number, string>>({});
const [plans, setPlans] = useState<MembershipPlan[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState("");
  const [payingPlanId, setPayingPlanId] = useState<number | null>(null);
const [membershipMessage, setMembershipMessage] = useState("");
const [purchaseSuccess, setPurchaseSuccess] = useState(false);

  const loadMemberships = useCallback(async () => {
  if (!customerToken) {
    setLoading(false);
    return;
  }

  setLoading(true);
  setError("");
  setMembershipQrs({});


  try {
    const response = await fetch(
      `${API_URL

      }/api/public/my-memberships`,
      {
        headers: {
          Authorization: `Bearer ${customerToken}`,
        },
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Unable to load memberships.");
    }

    const customerMemberships: Membership[] = data.memberships || [];

    setMemberships(customerMemberships);

    // Retrieve QR codes for eligible memberships.
    const eligibleMemberships = customerMemberships.filter(
      (item) =>
        ["active", "scheduled"].includes(item.status.toLowerCase())
    );

    const qrResults = await Promise.all(
      eligibleMemberships.map(async (item) => {
        try {
          const qrResponse = await fetch(
            `${API_URL}/api/access/membership/${item.membership_id}/qr`,
            {
              headers: {
                Authorization: `Bearer ${customerToken}`,
              },
            }
          );

          if (!qrResponse.ok) {
            const errorData = await qrResponse.json();

            console.error(
              `Membership QR error for ${item.membership_id}:`,
              errorData.detail
            );

            return null;
          }

          const qrData = await qrResponse.json();

          return {
            membershipId: item.membership_id,
            qrDataUrl: qrData.qr_data_url,
          };
        } catch (err) {
          console.error("Membership QR loading failed:", err);
          return null;
        }
      })
    );

    const qrMap: Record<number, string> = {};

    qrResults.forEach((result) => {
      if (result) {
        qrMap[result.membershipId] = result.qrDataUrl;
      }
    });

    setMembershipQrs(qrMap);

  } catch (err) {
    setError(
      err instanceof Error ? err.message : "Something went wrong."
    );
  } finally {
    setLoading(false);
  }
}, [customerToken]);

  useEffect(() => {
    if (!authLoading) {
      void loadMemberships();
    }
  }, [authLoading, loadMemberships]);

  useEffect(() => {
    fetch(`${API_URL}/api/public/membership-plans`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load plans.");
        return response.json();
      })
      .then((data) => setPlans(data))
      .catch((err) => console.error(err));
  }, []);



async function buyMembership(planId: number) {
  if (!customer || !customerToken) {
    setMembershipMessage("Please login to purchase membership.");
    return;
  }

  setPayingPlanId(planId);
  setMembershipMessage("");
  setPurchaseSuccess(false);

  try {
    const loaded = await loadRazorpayScript();

    if (!loaded) {
      throw new Error("Unable to load Razorpay Checkout.");
    }

    const orderResponse = await fetch(
      `${API_URL}/api/membership-payments/create-order?plan_id=${planId}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${customerToken}`,
        },
      }
    );

    const orderData = await orderResponse.json();

    if (!orderResponse.ok) {
      throw new Error(orderData.detail || "Unable to create membership order.");
    }

    await new Promise<void>((resolve, reject) => {
      const razorpay = new window.Razorpay({
        key: orderData.key_id,
        amount: orderData.amount,
        currency: orderData.currency,
        name: "The King Elite Arena",
        description: orderData.plan_name,
        order_id: orderData.order_id,

        prefill: {
          name: customer.full_name,
          contact: customer.phone ?? "",
        },

        handler: async (paymentResponse) => {
          try {
            const verifyResponse = await fetch(
              `${API_URL}/api/membership-payments/verify`,
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${customerToken}`,
                },
                body: JSON.stringify(paymentResponse),
              }
            );

            const verifyData = await verifyResponse.json();

            if (!verifyResponse.ok) {
              throw new Error(
                verifyData.detail || "Membership verification failed."
              );
            }

            setMembershipMessage(
              verifyData.membership_status === "scheduled"
                ? "Payment successful! Your membership is scheduled."
                : "Payment successful! Your membership is now active."
            );

            setPurchaseSuccess(true);
            await loadMemberships();
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
  } catch (error) {
    setMembershipMessage(
      error instanceof Error ? error.message : "Membership payment failed."
    );
  } finally {
    setPayingPlanId(null);
  }
}


  if (authLoading) {
    return <main className="my-membership-page">Checking your account...</main>;
  }

  if (!customer) {
    return (
      <main className="my-membership-page">
        <div className="membership-empty">
          <h2>Login Required</h2>
          <p>Please login to view your membership.</p>
          <a href="/book" className="membership-button">
            Login to Continue
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="my-membership-page">
      <div className="my-membership-container">

        <a href="/" className="membership-back">
          ← Back to Home
        </a>



<header className="membership-page-header">
  <div className="membership-header-top">
    <span className="membership-eyebrow">
      YOUR ACCOUNT
    </span>

    <button
      className="membership-refresh"
      onClick={() => void loadMemberships()}
      disabled={loading}
    >
      {loading ? "Loading..." : "↻ Refresh"}
    </button>
  </div>

  <div className="membership-header-content">
    <h1>My Membership</h1>
    <p>
      Welcome back, {customer.full_name}. Manage your arena
      membership and track your playing hours.
    </p>
  </div>
</header>



        {loading ? (
  <div className="membership-empty" role="status">
    <span className="membership-loading-mark">♛</span>
    <h2>Loading your membership</h2>
    <p>Please wait while we retrieve your membership details.</p>
  </div>
        ) : error ? (
          <div className="membership-empty">
            <p>{error}</p>
            <button onClick={() => void loadMemberships()}>
              Try Again
            </button>
          </div>
        ) : memberships.length === 0 ? (
          <section className="membership-empty">
            <span className="membership-empty-icon">♛</span>
            <h2>No Membership Yet</h2>
            <p>
              Choose a membership plan and enjoy more playing hours
              at The King Elite Arena.
            </p>
          </section>
        ) : (
          <section className="customer-membership-list">
            {memberships.map((item) => {
              const usedPercentage =
                item.total_hours > 0
                  ? Math.min(
                      100,
                      (item.used_hours / item.total_hours) * 100
                    )
                  : 0;

              return (
                <article

                  className="customer-membership-card"
                  key={item.membership_id}
                >
                  <div className="membership-main-content">
                  <div className="customer-membership-top">
                    <div>
                      <span className="membership-card-label">
                        THE KING ELITE ARENA
                      </span>
                      <h2>{item.plan_name}</h2>
                      <p>Membership ID: #{item.membership_id}</p>
                    </div>

                    <span
                      className={`membership-status status-${item.status.toLowerCase()}`}
                    >
                      {item.status}
                    </span>
                  </div>

                  <div className="membership-price">
                    ₹{Number(item.amount_paid).toLocaleString("en-IN")}
                    <span> Paid</span>
                  </div>

                  <div className="membership-hours-grid">
                    <div>
                      <span>Total Hours</span>
                      <strong>{item.total_hours}</strong>
                    </div>
                    <div>
                      <span>Used Hours</span>
                      <strong>{item.used_hours}</strong>
                    </div>
                    <div>
                      <span>Reserved Hours</span>
                      <strong>{item.reserved_hours}</strong>
                    </div>
                    <div>
                      <span>Remaining Hours</span>
                      <strong className="remaining-hours">
                        {item.remaining_hours}
                      </strong>
                    </div>
                  </div>

                  <div className="membership-progress-section">
                    <div className="membership-progress-heading">
                      <span>Playing Hours Used</span>
                      <strong>{Math.round(usedPercentage)}%</strong>
                    </div>

                    <div className="membership-progress-track">
                      <div
                        className="membership-progress-fill"
                        style={{ width: `${usedPercentage}%` }}
                      />
                    </div>
                  </div>

                  <div className="membership-validity">
                    <div>
                      <span>Start Date</span>
                      <strong>{formatDate(item.start_date)}</strong>
                    </div>
                    <div>
                      <span>Expiry Date</span>
                      <strong>{formatDate(item.expiry_date)}</strong>
                    </div>
                  </div>
                  </div>
                  {membershipQrs[item.membership_id] && (
  <div className="membership-qr-section">
    <h3>Your Membership QR Code</h3>

    <p>
      Show this QR code to arena staff when you visit.
    </p>

    <img
      src={membershipQrs[item.membership_id]}
      alt={`Membership QR for ${item.plan_name}`}
    />

    <p className="membership-qr-note">
      Keep this QR code ready for membership verification.
    </p>
  </div>
)}
                </article>
              );
            })}
          </section>
        )}

        {plans.length > 0 && (
          <section className="membership-more-plans">
            <div>
              <span className="membership-eyebrow">MORE PLAYING HOURS</span>
              <h2>Explore Membership Plans</h2>
              <p>Looking for another plan? Explore our available options.</p>
            </div>

            <div className="membership-more-grid">
              {plans.map((plan) => (
                <article key={plan.id}>
                  <h3>{plan.name}</h3>
                  <strong>
                    ₹{Number(plan.price).toLocaleString("en-IN")}
                  </strong>
                  <p>{plan.description}</p>
                  <span>
                    {plan.included_hours} Hours · {plan.validity_days} Days
                  </span>
                  <button
  type="button"
  className="membership-button"
  onClick={() => void buyMembership(plan.id)}
  disabled={payingPlanId !== null}
>
  {payingPlanId === plan.id ? "Opening Payment..." : "Purchase Plan"}
</button>
                </article>
              ))}
            </div>
            {membershipMessage && (
  <div
    className={`membership-payment-message ${
      purchaseSuccess ? "is-success" : "is-error"
    }`}
    role={purchaseSuccess ? "status" : "alert"}
    aria-live="polite"
  >
    <p>{membershipMessage}</p>

    {purchaseSuccess && (
      <button
        type="button"
        className="membership-button"
        onClick={() => {
          setPurchaseSuccess(false);
          setMembershipMessage("");
        }}
      >
        Continue
      </button>
    )}
  </div>
)}
          </section>
        )}

      </div>
    </main>
  );
}
