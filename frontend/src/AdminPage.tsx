
import { useEffect, useState } from "react";
import "./AdminPage.css";
import API_URL from "./api";

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
type PricingRule = {
  id?: number;
  hour_from: number;
  hour_to: number | null;
  price_per_player: number;
  is_active?: boolean;
};

type SportPricingSchedule = {
  sport_id: number;
  sport_name: string;
  is_active: boolean;
  rules: PricingRule[];
};

type PricingResponse = {
  sports: SportPricingSchedule[];
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
  payment_status: "unpaid" | "paid" | "failed" | "refunded" | "waived";
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

type MembershipPlan = {
  id: number;
  name: string;
  description: string | null;
  price: number;
  validity_days: number;
  included_hours: number;
  is_active: boolean;
  display_order: number;
  created_at: string;
};

type MembershipPlanForm = {
  name: string;
  description: string;
  price: number;
  validity_days: number;
  included_hours: number;
  is_active: boolean;
  display_order: number;
};

const EMPTY_MEMBERSHIP_FORM: MembershipPlanForm = {
  name: "",
  description: "",
  price: 1500,
  validity_days: 30,
  included_hours: 30,
  is_active: true,
  display_order: 1,
};


type Coupon = {
  id: number;
  code: string;
  description: string | null;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  applies_to: "booking" | "membership" | "both";
  min_order_amount: number;
  max_discount_amount: number | null;
  starts_at: string;
  ends_at: string;
  usage_limit: number | null;
  per_customer_limit: number | null;
  is_active: boolean;
  used_count: number;
  remaining_uses: number | null;
  created_at: string;
};

type CouponRedemption = {
  id: number;
  coupon_code: string;
  customer_name: string;
  customer_phone: string;
  applies_to: string;
  booking_id: number | null;
  membership_id: number | null;
  original_amount: number;
  discount_amount: number;
  final_amount: number;
  status: string;
  created_at: string;
};

type CouponForm = {
  code: string;
  description: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  applies_to: "booking" | "membership" | "both";
  min_order_amount: number;
  max_discount_amount: string;
  starts_at: string;
  ends_at: string;
  usage_limit: string;
  per_customer_limit: string;
  is_active: boolean;
};

function toLocalDateTimeInput(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function createEmptyCouponForm(): CouponForm {
  const start = new Date();
  const end = new Date(start.getTime() + 30 * 24 * 60 * 60 * 1000);
  return {
    code: "",
    description: "",
    discount_type: "percentage",
    discount_value: 10,
    applies_to: "both",
    min_order_amount: 0,
    max_discount_amount: "",
    starts_at: toLocalDateTimeInput(start),
    ends_at: toLocalDateTimeInput(end),
    usage_limit: "",
    per_customer_limit: "",
    is_active: true,
  };
}



export default function AdminPage() {
  const [token, setToken] = useState<string | null>(
  () => sessionStorage.getItem("admin_access_token")
);

const [username, setUsername] = useState("");
const [password, setPassword] = useState("");
const [loginLoading, setLoginLoading] = useState(false);
const [loginError, setLoginError] = useState("");

  const [config, setConfig] = useState<AdminConfig | null>(null);

  const [, setLoading] = useState(false);
  const [savingFacility, setSavingFacility] = useState(false);
  const [pricingSchedules, setPricingSchedules] = useState<
  SportPricingSchedule[]
>([]);
  const [pricingLoading, setPricingLoading] = useState(false);
  const [pricingSaving, setPricingSaving] = useState<number | null>(null);
  const [pricingError, setPricingError] = useState("");

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
  // Membership management
const [membershipPlans, setMembershipPlans] = useState<MembershipPlan[]>([]);
const [membershipLoading, setMembershipLoading] = useState(false);
const [membershipSaving, setMembershipSaving] = useState(false);
const [editingMembershipId, setEditingMembershipId] = useState<number | null>(null);
const [membershipForm, setMembershipForm] =
  useState<MembershipPlanForm>(EMPTY_MEMBERSHIP_FORM);
const [membershipError, setMembershipError] = useState("");


  // Coupon management
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [couponLoading, setCouponLoading] = useState(false);
  const [couponSaving, setCouponSaving] = useState(false);
  const [couponError, setCouponError] = useState("");
  const [couponForm, setCouponForm] = useState<CouponForm>(createEmptyCouponForm);
  const [editingCouponId, setEditingCouponId] = useState<number | null>(null);
  const [redemptions, setRedemptions] = useState<CouponRedemption[]>([]);
  const [redemptionsLoading, setRedemptionsLoading] = useState(false);

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
  
 

  useEffect(() => {
  if (!token) return;

  const expiry = Number(
    sessionStorage.getItem("admin_token_expires_at")
  );

  if (!expiry || expiry <= Date.now()) {
    logout();
    return;
  }

  let cancelled = false;

  async function validateSession() {
    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Session expired. Please log in again.");
      }

      if (!cancelled) {
        await loadSettings();
      }
    } catch {
      if (!cancelled) {
        logout();
        setLoginError("Your session has expired. Please log in again.");
      }
    }
  }

  void validateSession();

  const timeoutId = window.setTimeout(
    logout,
    expiry - Date.now()
  );

  return () => {
    cancelled = true;
    window.clearTimeout(timeoutId);
  };
}, [token]);

  async function apiRequest<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token
  ? { Authorization: `Bearer ${token}` }
  : {}),
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

await Promise.all([
  loadBookings(1),
  loadSummary(),
  loadMembershipPlans(),
  loadCoupons(),
  loadPricing(),
]);

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

  async function loadMembershipPlans() {
  setMembershipLoading(true);
  setMembershipError("");

  try {
    const data = await apiRequest<MembershipPlan[]>(
      "/api/admin/memberships/plans"
    );

    setMembershipPlans(data);
  } catch (err) {
    setMembershipError(
      err instanceof Error
        ? err.message
        : "Unable to load membership plans."
    );
  } finally {
    setMembershipLoading(false);
  }
}


async function loadCoupons() {
  setCouponLoading(true);
  setCouponError("");
  try {
    const data = await apiRequest<Coupon[]>("/api/admin/coupons");
    setCoupons(data);
  } catch (err) {
    setCouponError(err instanceof Error ? err.message : "Unable to load coupons.");
  } finally {
    setCouponLoading(false);
  }
}


// Load pricing schedules for all sports
async function loadPricing() {
  setPricingLoading(true);
  setPricingError("");

  try {
    const data = await apiRequest<PricingResponse>("/api/admin/pricing");
    setPricingSchedules(data.sports);
  } catch (err) {
    setPricingError(
      err instanceof Error ? err.message : "Unable to load pricing rules."
    );
  } finally {
    setPricingLoading(false);
  }
}

// Update a particular pricing rule
function updatePricingRule(
  sportId: number,
  ruleIndex: number,
  changes: Partial<PricingRule>
) {
  setPricingSchedules((current) =>
    current.map((schedule) =>
      schedule.sport_id === sportId
        ? {
            ...schedule,
            rules: schedule.rules.map((rule, index) =>
              index === ruleIndex ? { ...rule, ...changes } : rule
            ),
          }
        : schedule
    )
  );
}

// Add a new hourly pricing slab
function addPricingRule(sportId: number) {
  setPricingSchedules((current) =>
    current.map((schedule) => {
      if (schedule.sport_id !== sportId) return schedule;

      const rules = [...schedule.rules];
      const lastRule = rules[rules.length - 1];

      if (!lastRule || lastRule.hour_to !== null) return schedule;

      const nextHour = lastRule.hour_from + 1;

      rules[rules.length - 1] = {
        ...lastRule,
        hour_to: lastRule.hour_from,
      };

      rules.push({
        hour_from: nextHour,
        hour_to: null,
        price_per_player: lastRule.price_per_player,
        is_active: true,
      });

      return { ...schedule, rules };
    })
  );
}

// Remove a pricing slab and merge its range with the previous slab
function removePricingRule(sportId: number, ruleIndex: number) {
  setPricingSchedules((current) =>
    current.map((schedule) => {
      if (schedule.sport_id !== sportId || ruleIndex === 0) {
        return schedule;
      }

      const rules = [...schedule.rules];
      const removedRule = rules[ruleIndex];

      if (!removedRule) return schedule;

      rules[ruleIndex - 1] = {
        ...rules[ruleIndex - 1],
        hour_to: removedRule.hour_to,
      };

      rules.splice(ruleIndex, 1);

      return { ...schedule, rules };
    })
  );
}

// Save the complete pricing schedule to the backend
async function savePricing(schedule: SportPricingSchedule) {
  setPricingSaving(schedule.sport_id);
  setPricingError("");
  setMessage("");

  try {
    const payload = {
      rules: schedule.rules.map((rule) => ({
        hour_from: Number(rule.hour_from),
        hour_to:
          rule.hour_to === null || rule.hour_to === undefined
            ? null
            : Number(rule.hour_to),
        price_per_player: Number(rule.price_per_player),
      })),
    };

    const result = await apiRequest<{ message: string }>(
      `/api/admin/pricing/${schedule.sport_id}/rules`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      }
    );

    setMessage(`${schedule.sport_name}: ${result.message}`);

    // Refresh pricing schedules after successful save
    await loadPricing();
  } catch (err) {
    setPricingError(
      err instanceof Error ? err.message : "Unable to save pricing rules."
    );
  } finally {
    setPricingSaving(null);
  }
}


async function loadCouponRedemptions() {
  setRedemptionsLoading(true);
  setCouponError("");
  try {
    const data = await apiRequest<CouponRedemption[]>(
      "/api/admin/coupons/redemptions/history"
    );
    setRedemptions(data);
  } catch (err) {
    setCouponError(err instanceof Error ? err.message : "Unable to load redemption history.");
  } finally {
    setRedemptionsLoading(false);
  }
}

function resetCouponForm() {
  setCouponForm(createEmptyCouponForm());
  setEditingCouponId(null);
  setCouponError("");
}

function editCoupon(coupon: Coupon) {
  setEditingCouponId(coupon.id);
  setCouponForm({
    code: coupon.code,
    description: coupon.description ?? "",
    discount_type: coupon.discount_type,
    discount_value: coupon.discount_value,
    applies_to: coupon.applies_to,
    min_order_amount: coupon.min_order_amount,
    max_discount_amount: coupon.max_discount_amount === null ? "" : String(coupon.max_discount_amount),
    starts_at: toLocalDateTimeInput(new Date(coupon.starts_at)),
    ends_at: toLocalDateTimeInput(new Date(coupon.ends_at)),
    usage_limit: coupon.usage_limit === null ? "" : String(coupon.usage_limit),
    per_customer_limit: coupon.per_customer_limit === null ? "" : String(coupon.per_customer_limit),
    is_active: coupon.is_active,
  });
  setCouponError("");
}

async function saveCoupon(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();
  setCouponSaving(true);
  setCouponError("");
  setMessage("");

  try {
    const payload = {
      code: couponForm.code.trim().toUpperCase(),
      description: couponForm.description.trim() || null,
      discount_type: couponForm.discount_type,
      discount_value: Number(couponForm.discount_value),
      applies_to: couponForm.applies_to,
      min_order_amount: Number(couponForm.min_order_amount),
      max_discount_amount: couponForm.max_discount_amount.trim() ? Number(couponForm.max_discount_amount) : null,
      starts_at: new Date(couponForm.starts_at).toISOString(),
      ends_at: new Date(couponForm.ends_at).toISOString(),
      usage_limit: couponForm.usage_limit.trim() ? Number(couponForm.usage_limit) : null,
      per_customer_limit: couponForm.per_customer_limit.trim() ? Number(couponForm.per_customer_limit) : null,
      is_active: couponForm.is_active,
    };

    const result = await apiRequest<{ message: string }>(
      editingCouponId !== null ? `/api/admin/coupons/${editingCouponId}` : "/api/admin/coupons",
      {
        method: editingCouponId !== null ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      }
    );
    setMessage(result.message);
    resetCouponForm();
    await loadCoupons();
  } catch (err) {
    setCouponError(err instanceof Error ? err.message : "Unable to save coupon.");
  } finally {
    setCouponSaving(false);
  }
}

async function toggleCouponStatus(coupon: Coupon) {
  const activate = !coupon.is_active;
  if (!window.confirm(`Are you sure you want to ${activate ? "activate" : "deactivate"} ${coupon.code}?`)) return;
  setCouponError("");
  try {
    if (activate) {
      await apiRequest(`/api/admin/coupons/${coupon.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: true }),
      });
    } else {
      await apiRequest(`/api/admin/coupons/${coupon.id}`, { method: "DELETE" });
    }
    setMessage(`Coupon ${activate ? "activated" : "deactivated"} successfully.`);
    await loadCoupons();
  } catch (err) {
    setCouponError(err instanceof Error ? err.message : "Unable to update coupon status.");
  }
}

function resetMembershipForm() {
  setMembershipForm(EMPTY_MEMBERSHIP_FORM);
  setEditingMembershipId(null);
}

function editMembershipPlan(plan: MembershipPlan) {
  setEditingMembershipId(plan.id);

  setMembershipForm({
    name: plan.name,
    description: plan.description ?? "",
    price: plan.price,
    validity_days: plan.validity_days,
    included_hours: plan.included_hours,
    is_active: plan.is_active,
    display_order: plan.display_order,
  });
}

async function saveMembershipPlan(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();

  setMembershipSaving(true);
  setMembershipError("");
  setMessage("");

  try {
    const isEditing = editingMembershipId !== null;

    const result = await apiRequest<{ message: string }>(
      isEditing
        ? `/api/admin/memberships/plans/${editingMembershipId}`
        : "/api/admin/memberships/plans",
      {
        method: isEditing ? "PATCH" : "POST",
        body: JSON.stringify({
          ...membershipForm,
          price: Number(membershipForm.price),
          validity_days: Number(membershipForm.validity_days),
          included_hours: Number(membershipForm.included_hours),
          display_order: Number(membershipForm.display_order),
        }),
      }
    );

    setMessage(result.message);
    resetMembershipForm();
    await loadMembershipPlans();
  } catch (err) {
    setMembershipError(
      err instanceof Error ? err.message : "Unable to save membership plan."
    );
  } finally {
    setMembershipSaving(false);
  }
}

async function toggleMembershipStatus(plan: MembershipPlan) {
  const action = plan.is_active ? "deactivate" : "activate";

  if (!window.confirm(`Are you sure you want to ${action} ${plan.name}?`)) {
    return;
  }

  setMembershipError("");

  try {
    await apiRequest(
      `/api/admin/memberships/plans/${plan.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ is_active: !plan.is_active }),
      }
    );

    setMessage(`Membership plan ${action}d successfully.`);
    await loadMembershipPlans();
  } catch (err) {
    setMembershipError(
      err instanceof Error ? err.message : "Unable to update membership status."
    );
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
  }, [token]);

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

  function logout() {
  sessionStorage.removeItem("admin_access_token");
  sessionStorage.removeItem("admin_token_expires_at");

  setToken(null);
  setPassword("");
  setConfig(null);
  setBookings([]);
  setBookingTotal(0);
  setSummary(null);
  setMembershipPlans([]);
  setCoupons([]);
  setRedemptions([]);
  resetCouponForm();
  setMessage("");
  setError("");
  setLoginError("");
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

       <div className="admin-header-actions">
  {token && (
    <button
      type="button"
      className="admin-secondary-button"
      onClick={logout}
    >
      Logout
    </button>
  )}

  <a className="admin-back-link" href="/">
    View website ↗
  </a>
</div>
      </header>

      <section className="admin-main">
        <div className="admin-title">
          <span className="admin-eyebrow">ARENA MANAGEMENT</span>
          <h1>
            Admin <span>Dashboard</span>
          </h1>
          <p>Manage bookings, payments, facility settings, and sports pricing.</p>
        </div>

        {!token && (
  <section className="admin-panel admin-auth-panel">
    <div>
      <h2>Admin Login</h2>
      <p>Enter your admin username and password to access the dashboard.</p>
    </div>

    <form
      className="admin-key-form"
      onSubmit={async (event) => {
        event.preventDefault();
        setLoginLoading(true);
        setLoginError("");

        try {
          const response = await fetch(`${API_URL}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
          });

          const data = await response.json();

          if (!response.ok) {
            throw new Error(data.detail || "Login failed.");
          }

          sessionStorage.setItem("admin_access_token", data.access_token);

sessionStorage.setItem(
  "admin_token_expires_at",
  String(Date.now() + data.expires_in * 1000)
);

setToken(data.access_token);
setPassword("");

        } catch (err) {
          setLoginError(
            err instanceof Error ? err.message : "Unable to login."
          );
        } finally {
          setLoginLoading(false);
        }
      }}
    >
      <input
        type="text"
        autoComplete="username"
        placeholder="Admin username"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        required
      />

      <input
        type="password"
        autoComplete="current-password"
        placeholder="Admin password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        required
      />

      {loginError && (
        <div className="admin-alert admin-error">{loginError}</div>
      )}

      <button type="submit" disabled={loginLoading}>
        {loginLoading ? "Logging in..." : "Login"}
      </button>
    </form>
  </section>
)}

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
                  <option value="waived">Coupon / waived</option>
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
                              booking.payment_status === "waived" ||
                              updatingBooking === `${booking.booking_reference}-payment`
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
                            <option value="waived" disabled>Coupon / waived</option>
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

            {/* MEMBERSHIP MANAGEMENT */}
<section className="admin-panel">
  <div className="admin-section-heading">
    <div>
      <span className="admin-eyebrow">MEMBERSHIP</span>
      <h2>Membership Management</h2>
      <p>Create and manage membership plans for both sports.</p>
    </div>

    <span className="admin-tag">
      {membershipPlans.length} plans
    </span>
  </div>

  {membershipError && (
    <div className="admin-alert admin-error">{membershipError}</div>
  )}
  <form className="admin-form-grid" onSubmit={saveMembershipPlan}>
  <label className="admin-field admin-full-field">
    Membership name
    <input
      value={membershipForm.name}
      onChange={(e) =>
        setMembershipForm({ ...membershipForm, name: e.target.value })
      }
      placeholder="e.g. Monthly Membership"
      required
      maxLength={100}
    />
  </label>

  <label className="admin-field admin-full-field">
    Description
    <textarea
      value={membershipForm.description}
      onChange={(e) =>
        setMembershipForm({ ...membershipForm, description: e.target.value })
      }
      placeholder="Describe membership benefits"
    />
  </label>

  <label className="admin-field">
    Price (₹)
    <input
      type="number"
      min="0"
      step="0.01"
      value={membershipForm.price}
      onChange={(e) =>
        setMembershipForm({ ...membershipForm, price: Number(e.target.value) })
      }
      required
    />
  </label>

  <label className="admin-field">
    Validity (days)
    <input
      type="number"
      min="1"
      value={membershipForm.validity_days}
      onChange={(e) =>
        setMembershipForm({
          ...membershipForm,
          validity_days: Number(e.target.value),
        })
      }
      required
    />
  </label>

  <label className="admin-field">
    Playing hours
    <input
      type="number"
      min="0.01"
      step="0.01"
      value={membershipForm.included_hours}
      onChange={(e) =>
        setMembershipForm({
          ...membershipForm,
          included_hours: Number(e.target.value),
        })
      }
      required
    />
  </label>

  <label className="admin-field">
    Display order
    <input
      type="number"
      min="0"
      value={membershipForm.display_order}
      onChange={(e) =>
        setMembershipForm({
          ...membershipForm,
          display_order: Number(e.target.value),
        })
      }
    />
  </label>

  <label className="admin-active-toggle">
    <input
      type="checkbox"
      checked={membershipForm.is_active}
      onChange={(e) =>
        setMembershipForm({
          ...membershipForm,
          is_active: e.target.checked,
        })
      }
    />
    Active plan
  </label>

  <div className="admin-full-field">
    <button type="submit" className="admin-primary-button" disabled={membershipSaving}>
      {membershipSaving
        ? "Saving..."
        : editingMembershipId !== null
          ? "Update membership plan"
          : "Create membership plan"}
    </button>

    {editingMembershipId !== null && (
      <button
        type="button"
        className="admin-secondary-button"
        onClick={resetMembershipForm}
      >
        Cancel editing
      </button>
    )}
  </div>
</form>

  <div className="admin-booking-toolbar">
    <span>
      {membershipLoading
        ? "Loading membership plans..."
        : `${membershipPlans.length} membership plans`}
    </span>

    <button
      type="button"
      className="admin-secondary-button"
      onClick={() => void loadMembershipPlans()}
      disabled={membershipLoading}
    >
      Refresh plans
    </button>
  </div>

  <div className="admin-sports-list">
    {membershipPlans.map((plan) => (
      <article className="admin-sport-card" key={plan.id}>
        <div className="admin-sport-info">
          <div>
            <h3>{plan.name}</h3>
            <span className={plan.is_active ? "admin-status active" : "admin-status inactive"}>
              {plan.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        </div>

        <div>
  <strong>₹{Number(plan.price).toLocaleString("en-IN")}</strong>
  <p>
    {plan.validity_days} days · {plan.included_hours} playing hours
  </p>
  <small>{plan.description}</small>

  <div className="admin-sport-controls">
    <button
      type="button"
      className="admin-secondary-button"
      onClick={() => editMembershipPlan(plan)}
    >
      Edit Plan
    </button>

    <button
      type="button"
      className="admin-primary-button"
      onClick={() => void toggleMembershipStatus(plan)}
    >
      {plan.is_active ? "Deactivate" : "Activate"}
    </button>
  </div>
</div>
      </article>
    ))}

    {!membershipPlans.length && !membershipLoading && (
      <p className="admin-help">No membership plans found.</p>
    )}
  </div>
</section>

            {/* COUPON MANAGEMENT */}
            <section className="admin-panel">
              <div className="admin-section-heading">
                <div>
                  <span className="admin-eyebrow">PROMOTIONS</span>
                  <h2>Coupon Management</h2>
                  <p>Create discount codes and review their usage.</p>
                </div>
                <span className="admin-tag">{coupons.length} coupons</span>
              </div>

              {couponError && <div className="admin-alert admin-error">{couponError}</div>}

              <form className="admin-form-grid coupon-form" onSubmit={saveCoupon}>
                <label className="admin-field">
                  Coupon code
                  <input
                    value={couponForm.code}
                    onChange={(e) => setCouponForm({ ...couponForm, code: e.target.value.toUpperCase() })}
                    placeholder="e.g. WELCOME100"
                    minLength={3}
                    maxLength={40}
                    pattern="[A-Za-z0-9_-]+"
                    required
                  />
                </label>

                <label className="admin-field">
                  Discount type
                  <select
                    value={couponForm.discount_type}
                    onChange={(e) => setCouponForm({ ...couponForm, discount_type: e.target.value as CouponForm["discount_type"] })}
                  >
                    <option value="percentage">Percentage (%)</option>
                    <option value="fixed">Fixed amount (₹)</option>
                  </select>
                </label>

                <label className="admin-field">
                  Discount value {couponForm.discount_type === "percentage" ? "(%)" : "(₹)"}
                  <input
                    type="number"
                    min="0.01"
                    max={couponForm.discount_type === "percentage" ? "100" : undefined}
                    step="0.01"
                    value={couponForm.discount_value}
                    onChange={(e) => setCouponForm({ ...couponForm, discount_value: Number(e.target.value) })}
                    required
                  />
                </label>

                <label className="admin-field">
                  Applies to
                  <select
                    value={couponForm.applies_to}
                    onChange={(e) => setCouponForm({ ...couponForm, applies_to: e.target.value as CouponForm["applies_to"] })}
                  >
                    <option value="both">Bookings and memberships</option>
                    <option value="booking">Court bookings only</option>
                    <option value="membership">Memberships only</option>
                  </select>
                </label>

                <label className="admin-field">
                  Minimum purchase (₹)
                  <input type="number" min="0" step="0.01" value={couponForm.min_order_amount} onChange={(e) => setCouponForm({ ...couponForm, min_order_amount: Number(e.target.value) })} required />
                </label>

                <label className="admin-field">
                  Maximum discount (₹, optional)
                  <input type="number" min="0.01" step="0.01" value={couponForm.max_discount_amount} onChange={(e) => setCouponForm({ ...couponForm, max_discount_amount: e.target.value })} placeholder="No maximum" />
                </label>

                <label className="admin-field">
                  Starts at
                  <input type="datetime-local" value={couponForm.starts_at} onChange={(e) => setCouponForm({ ...couponForm, starts_at: e.target.value })} required />
                </label>

                <label className="admin-field">
                  Ends at
                  <input type="datetime-local" value={couponForm.ends_at} onChange={(e) => setCouponForm({ ...couponForm, ends_at: e.target.value })} required />
                </label>

                <label className="admin-field">
                  Total usage limit (optional)
                  <input type="number" min="1" step="1" value={couponForm.usage_limit} onChange={(e) => setCouponForm({ ...couponForm, usage_limit: e.target.value })} placeholder="Unlimited" />
                </label>

                <label className="admin-field">
                  Per-customer limit (optional)
                  <input type="number" min="1" step="1" value={couponForm.per_customer_limit} onChange={(e) => setCouponForm({ ...couponForm, per_customer_limit: e.target.value })} placeholder="Unlimited" />
                </label>

                <label className="admin-field admin-full-field">
                  Description (optional)
                  <textarea value={couponForm.description} maxLength={300} onChange={(e) => setCouponForm({ ...couponForm, description: e.target.value })} placeholder="Short internal or customer-facing description" />
                </label>

                <label className="admin-active-toggle admin-full-field coupon-active-toggle">
                  <input type="checkbox" checked={couponForm.is_active} onChange={(e) => setCouponForm({ ...couponForm, is_active: e.target.checked })} />
                  Active immediately
                </label>

                <div className="admin-full-field coupon-form-actions">
                  <button type="submit" disabled={couponSaving}>
                    {couponSaving ? "Saving..." : editingCouponId !== null ? "Update coupon" : "Create coupon"}
                  </button>
                  {editingCouponId !== null && <button type="button" className="admin-secondary-button" onClick={resetCouponForm}>Cancel editing</button>}
                </div>
              </form>

              <div className="admin-booking-toolbar coupon-toolbar">
                <span>{couponLoading ? "Loading coupons..." : `${coupons.length} coupons created`}</span>
                <button type="button" className="admin-secondary-button" onClick={() => void loadCoupons()} disabled={couponLoading}>Refresh coupons</button>
              </div>

              <div className="coupon-list">
                {coupons.map((coupon) => (
                  <article className="coupon-card" key={coupon.id}>
                    <div className="coupon-card-heading">
                      <div>
                        <strong className="coupon-code">{coupon.code}</strong>
                        <span className={coupon.is_active ? "admin-status active" : "admin-status inactive"}>{coupon.is_active ? "Active" : "Inactive"}</span>
                      </div>
                      <strong className="coupon-discount">
                        {coupon.discount_type === "percentage" ? `${coupon.discount_value}% OFF` : `₹${coupon.discount_value} OFF`}
                      </strong>
                    </div>
                    <p>{coupon.description || "No description"}</p>
                    <div className="coupon-meta">
                      <span>Applies: {coupon.applies_to === "both" ? "Bookings + memberships" : coupon.applies_to}</span>
                      <span>Used: {coupon.used_count}{coupon.usage_limit !== null ? ` / ${coupon.usage_limit}` : " / Unlimited"}</span>
                      <span>Per customer: {coupon.per_customer_limit ?? "Unlimited"}</span>
                      <span>Min. purchase: ₹{Number(coupon.min_order_amount).toFixed(2)}</span>
                      <span>Valid until: {new Date(coupon.ends_at).toLocaleString()}</span>
                    </div>
                    <div className="coupon-card-actions">
                      <button type="button" className="admin-secondary-button" onClick={() => editCoupon(coupon)}>Edit</button>
                      <button type="button" onClick={() => void toggleCouponStatus(coupon)}>{coupon.is_active ? "Deactivate" : "Activate"}</button>
                    </div>
                  </article>
                ))}
                {!coupons.length && !couponLoading && <p className="admin-help">No coupons created yet. Use the form above to create your first coupon.</p>}
              </div>

              <div className="coupon-history-heading">
                <div>
                  <h3>Redemption History</h3>
                  <p>Review coupon usage by customers.</p>
                </div>
                <button type="button" className="admin-secondary-button" onClick={() => void loadCouponRedemptions()} disabled={redemptionsLoading}>{redemptionsLoading ? "Loading..." : "Load history"}</button>
              </div>
              {redemptions.length > 0 && (
                <div className="admin-bookings-table-wrap">
                  <table className="admin-bookings-table">
                    <thead><tr><th>Coupon</th><th>Customer</th><th>Purchase</th><th>Original</th><th>Discount</th><th>Final</th><th>Status</th><th>Date</th></tr></thead>
                    <tbody>
                      {redemptions.map((item) => (
                        <tr key={item.id}>
                          <td><strong>{item.coupon_code}</strong></td>
                          <td>{item.customer_name}<small>{item.customer_phone}</small></td>
                          <td>{item.applies_to}</td>
                          <td>₹{item.original_amount.toFixed(2)}</td>
                          <td>₹{item.discount_amount.toFixed(2)}</td>
                          <td>₹{item.final_amount.toFixed(2)}</td>
                          <td>{item.status}</td>
                          <td>{new Date(item.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!redemptions.length && !redemptionsLoading && <p className="admin-help">Redemption history has not been loaded yet.</p>}
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
      <h2>Flexible Sports Pricing</h2>
      <p>
        Configure hourly prices per player for each sport.
      </p>
    </div>

    <span className="admin-tag">
      {pricingSchedules.length} sports
    </span>
  </div>

  {pricingError && (
    <div className="admin-alert admin-error">{pricingError}</div>
  )}

  {pricingLoading ? (
    <p className="admin-help">Loading pricing schedules...</p>
  ) : (
    <div className="admin-sports-list">
      {pricingSchedules.map((schedule) => (
        <article
  className="admin-sport-card admin-pricing-card"
  key={schedule.sport_id}
>
          <div className="admin-sport-info">
            <span className="admin-sport-icon">
              {schedule.sport_name.toLowerCase() === "badminton"
                ? "🏸"
                : "🎾"}
            </span>

            <div>
              <h3>{schedule.sport_name}</h3>
              <span
                className={
                  schedule.is_active
                    ? "admin-status active"
                    : "admin-status inactive"
                }
              >
                {schedule.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </div>

          <div className="admin-pricing-rules">
            <div className="admin-pricing-header">
              <strong>Hourly pricing slabs</strong>

              <button
                type="button"
                className="admin-secondary-button"
                onClick={() => addPricingRule(schedule.sport_id)}
                disabled={
                  pricingSaving === schedule.sport_id ||
                  schedule.rules.length >= 20
                }
              >
                + Add slab
              </button>
            </div>

            {schedule.rules.map((rule, index) => (
              <div className="admin-pricing-rule" key={`${schedule.sport_id}-${index}`}>
                <label className="admin-field">
                  Hour from
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={rule.hour_from}
                    onChange={(event) =>
                      updatePricingRule(schedule.sport_id, index, {
                        hour_from: Number(event.target.value),
                      })
                    }
                  />
                </label>

                <label className="admin-field">
                  Hour to
                  <input
                    type="number"
                    min={rule.hour_from}
                    step="1"
                    value={rule.hour_to ?? ""}
                    placeholder="Unlimited"
                    disabled={rule.hour_to === null}
                    onChange={(event) =>
                      updatePricingRule(schedule.sport_id, index, {
                        hour_to: event.target.value
                          ? Number(event.target.value)
                          : null,
                      })
                    }
                  />
                </label>

                <label className="admin-field">
                  Price per player (₹)
                  <input
                    type="number"
                    min="0"
                    max="99999999"
                    step="0.01"
                    value={rule.price_per_player}
                    onChange={(event) =>
                      updatePricingRule(schedule.sport_id, index, {
                        price_per_player: Number(event.target.value),
                      })
                    }
                  />
                </label>

                <button
                  type="button"
                  className="admin-secondary-button"
                  onClick={() =>
                    removePricingRule(schedule.sport_id, index)
                  }
                  disabled={
                    index === 0 ||
                    schedule.rules.length === 1 ||
                    pricingSaving === schedule.sport_id
                  }
                >
                  Remove
                </button>
              </div>
            ))}

            <p className="admin-help">
              {schedule.rules.map((rule, index) => (
                <span key={index}>
                  {index > 0 ? " · " : ""}
                  {rule.hour_to === null
                    ? `Hour ${rule.hour_from} onwards`
                    : rule.hour_from === rule.hour_to
                      ? `Hour ${rule.hour_from}`
                      : `Hours ${rule.hour_from}–${rule.hour_to}`}
                  : ₹{Number(rule.price_per_player).toFixed(2)} per player
                </span>
              ))}
            </p>

            <button
              type="button"
              className="admin-primary-button"
              onClick={() => void savePricing(schedule)}
              disabled={
                pricingSaving !== null ||
                schedule.rules.length === 0
              }
            >
              {pricingSaving === schedule.sport_id
                ? "Saving pricing..."
                : "Save pricing rules"}
            </button>
          </div>
        </article>
      ))}

      {!pricingSchedules.length && (
        <p className="admin-help">No sport pricing schedules found.</p>
      )}
    </div>
  )}

  <p className="admin-help">
    Prices are calculated per player. All bookings must use full-hour
    durations. Changes apply to new bookings; existing booking snapshots
    remain unchanged.
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
