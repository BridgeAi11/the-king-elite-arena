  import { useEffect, useState } from "react";
  import kingArenaLogo from "./assets/king-elite-arena-logo.png";
  import "./App.css";
  import AdminPage from "./AdminPage";
  import BookingPage from "./BookingPage";
  import { CustomerAuthProvider, useCustomerAuth } from "./CustomerAuthContext";
  import MyBookingsPage from "./MyBookingsPage";
  import MyMembershipPage from "./MyMembershipPage";


  type MembershipPlan = {
    id: number;
    name: string;
    description: string | null;
    price: number;
    validity_days: number;
    included_hours: number;
    is_active: boolean;
    display_order: number;
  };

  type PricingRule = {
    hour_from: number;
    hour_to: number | null;
    price_per_player: number;
  };

  type PublicPricing = {
    sports: {
      sport_id: number;
      sport_name: string;
      rules: PricingRule[];
    }[];
  };


  type Facility = {
    facility_name: string;
    opening_time: string;
    closing_time: string;
    operating_days: string[];
    is_booking_enabled: boolean;
  };

  type PublicConfig = {
    facility: Facility;
    sports: {
      name: string;
      hourly_rate: number;
      is_active: boolean;
    }[];
  };

  function LandingPage() {
    const { customer, authLoading, logoutCustomer } = useCustomerAuth();
    const [menuOpen, setMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);

    const [facility, setFacility] = useState<Facility | null>(null);
    const [configError, setConfigError] = useState(false);
    const [membershipPlans, setMembershipPlans] = useState<MembershipPlan[]>([]);
    const [membershipLoading, setMembershipLoading] = useState(true);
    const [membershipError, setMembershipError] = useState("");

    const [pricing, setPricing] = useState<PublicPricing["sports"]>([]);
    const [pricingLoading, setPricingLoading] = useState(true);
    const [pricingError, setPricingError] = useState("");


    useEffect(() => {
      let cancelled = false;

      async function loadPublicConfig() {
        try {
          const response = await fetch(
            "http://127.0.0.1:8000/api/public/config"
          );

          if (!response.ok) {
            throw new Error("Unable to load public configuration");
          }

          const data: PublicConfig = await response.json();

          if (cancelled) return;

          setFacility(data.facility);
          setConfigError(false);
        } catch (error) {
          console.error("Failed to load arena settings:", error);
          if (!cancelled) setConfigError(true);
        }
      }

      loadPublicConfig();

      return () => {
        cancelled = true;
      };
    }, []);


  useEffect(() => {
    let cancelled = false;

    async function loadPublicPricing() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/public/pricing"
        );

        if (!response.ok) {
          throw new Error("Unable to load public pricing.");
        }

        const data: PublicPricing = await response.json();

        if (!cancelled) {
          setPricing(data.sports);
          setPricingError("");
        }
      } catch (error) {
        console.error("Failed to load public pricing:", error);

        if (!cancelled) {
          setPricingError("Pricing information is temporarily unavailable.");
        }
      } finally {
        if (!cancelled) {
          setPricingLoading(false);
        }
      }
    }

    void loadPublicPricing();

    return () => {
      cancelled = true;
    };
  }, []);


    useEffect(() => {
    let cancelled = false;

    async function loadMembershipPlans() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/public/membership-plans"
        );

        if (!response.ok) {
          throw new Error("Unable to load membership plans.");
        }

        const data: MembershipPlan[] = await response.json();

        if (!cancelled) {
          setMembershipPlans(data);
          setMembershipError("");
        }
      } catch (error) {
        console.error("Failed to load membership plans:", error);

        if (!cancelled) {
          setMembershipError("Membership plans are temporarily unavailable.");
        }
      } finally {
        if (!cancelled) {
          setMembershipLoading(false);
        }
      }
    }

    void loadMembershipPlans();

    return () => {
      cancelled = true;
    };
  }, []);

    const closeMenu = () => setMenuOpen(false);

    return (
      <main>
        <header className="site-header">
    <a className="brand" href="#home" onClick={closeMenu}>
      <img
        src={kingArenaLogo}
        alt="The King Elite Arena Logo"
        className="brand-logo"
      />

      <span className="brand-name">
        THE KING
        <strong>ELITE ARENA</strong>
      </span>
    </a>

    <button
      className="menu-toggle"
      type="button"
      aria-label={menuOpen ? "Close navigation" : "Open navigation"}
      aria-expanded={menuOpen}
      onClick={() => setMenuOpen(!menuOpen)}
    >
      {menuOpen ? "✕" : "☰"}
    </button>

    <nav
      id="main-navigation"
      className={`navigation ${menuOpen ? "navigation-open" : ""}`}
    >
      <a href="#pricing" onClick={closeMenu}>Pricing</a>
      <a href="#membership" onClick={closeMenu}>Membership</a>
      <a href="#contact" onClick={closeMenu}>Contact</a>

     
{customer ? (
  <>
    <a href="/my-bookings" onClick={closeMenu}>
      My Bookings
    </a>

    <a href="/my-membership" onClick={closeMenu}>
      My Membership
    </a>

    <div className="profile-menu-wrap">
      <button
        type="button"
        className="profile-menu-button"
        aria-expanded={profileMenuOpen}
        onClick={() => setProfileMenuOpen(!profileMenuOpen)}
      >
        <span className="profile-avatar">
          {customer.full_name.charAt(0).toUpperCase()}
        </span>

        <span className="profile-button-text">
          <strong>{customer.full_name}</strong>
          <small>{customer.phone}</small>
        </span>

        <span className="profile-chevron">
          {profileMenuOpen ? "⌃" : "⌄"}
        </span>
      </button>

      {profileMenuOpen && (
        <div className="profile-dropdown">
          <button
            type="button"
            className="profile-logout"
            onClick={() => {
              closeMenu();
              setProfileMenuOpen(false);
              logoutCustomer();
            }}
          >
            <span>↪</span> Logout
          </button>
        </div>
      )}
    </div>
  </>
) : (
  <a className="nav-login-link" href="/book" onClick={closeMenu}>
    {authLoading ? "Please wait..." : "Login"}
  </a>
)}


      <a className="nav-cta" href="/book" onClick={closeMenu}>
        Book a Slot <span>↗</span>
      </a>
    </nav>
  </header>

        <section className="hero" id="home">
          <div className="hero-content">
            <span className="eyebrow">
              <span className="status-dot" /> YOUR GAME. YOUR ARENA.
            </span>

            <h1>
              PLAY BIGGER.
              <br />
              DREAM <span>HIGHER.</span>
            </h1>

            <p className="hero-description">
              Your next great game starts here. Discover your passion,
              challenge your limits and play at The King Elite Arena.
            </p>

            <div className="hero-actions">
            <a className="button button-primary" href="/book">
    {customer ? "Book a Slot" : "Login to Book"}
    <span>↗</span>
  </a>
            
  <a className="button button-secondary recent-bookings-button" href="/my-bookings">
    My Recent Bookings <span>↗</span>
  </a>

   </div>

            <div className="hero-highlights">
              <div>
                <strong>06</strong>
                <span>Sports Courts</span>
              </div>
              <div>
                <strong>02</strong>
                <span>Sports to Play</span>
              </div>
              <div>
                <strong>07</strong>
                <span>Days a Week</span>
              </div>
            </div>
          </div>

          <div className="hero-visual" aria-label="Sports arena">
            <div className="hero-image">
              <img
                src="/arena-hero.jpg"
                alt="Indoor sports court at The King Elite Arena"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />
              <div className="image-overlay" />
              <div className="image-caption">
                <span>BUILT FOR THE GAME</span>
                <strong>YOUR MOMENT STARTS NOW.</strong>
              </div>
            </div>
            <div className="floating-card">
              <span className="floating-icon">♛</span>
              <div>
                <strong>Play Like a Champion</strong>
                <span>Every game. Every day.</span>
              </div>
            </div>
          </div>
        </section>

        

        <section className="pricing-section section" id="pricing">
          <div className="section-heading">
            <div>
              <span className="eyebrow">SIMPLE. CLEAR. AFFORDABLE.</span>
              <h2>Game On. <span>Pay Less.</span></h2>
            </div>
            <p>
              Straightforward hourly pricing. Choose your sport and get ready
              to play.
            </p>
          </div>

          


  <div className="pricing-grid">
    {pricingLoading ? (
      <p>Loading pricing information...</p>
    ) : pricingError ? (
      <p>{pricingError}</p>
    ) : pricing.length === 0 ? (
      <p>Pricing information is currently unavailable.</p>
    ) : (
      pricing.map((sport) => (
        <article className="pricing-card" key={sport.sport_id}>
          <span className="pricing-label">
            {sport.sport_name.toUpperCase()}
          </span>

          <div className="pricing-rules">
            {sport.rules.map((rule, index) => (
              <div className="pricing-rule" key={index}>
                <span>
                {rule.hour_from === 1 && index === 0
                  ? "First hour"
                  : rule.hour_to === null
                    ? "Every additional hour"
                    : rule.hour_from === rule.hour_to
                      ? `Hour ${rule.hour_from} — additional`
                      : `Hours ${rule.hour_from}–${rule.hour_to} — each`}
              </span>

                <strong>
                  ₹{rule.price_per_player.toLocaleString("en-IN")}
                  <small> / player</small>
                </strong>
              </div>
            ))}
          </div>

          <a className="button button-primary full-button" href="/book">
            Book Now <span>↗</span>
          </a>
        </article>
      ))
    )}
  </div>

  <p className="pricing-explanation">
    Pricing is cumulative. The first hour is charged at its listed rate.
    Each additional hour is charged at the applicable additional-hour rate.
    All prices are per player.
  </p>


          
        <p className="pricing-note">
          {configError
            ? "Live facility settings are temporarily unavailable."
            : facility
              ? `Opening hours: ${facility.opening_time}–${facility.closing_time}`
              : "Loading facility hours..."}
          {facility && (
            <>
              <br />
              Operating days: {facility.operating_days.join(", ")}
            </>
          )}
        </p>

        </section>

        <section className="membership-section section" id="membership">
    <div className="membership-content">
      <span className="eyebrow">PLAY MORE. SAVE MORE.</span>

      <h2>
        Make Every Game <span>Count.</span>
      </h2>

      <p>
        Become a member and enjoy more court time across badminton
        and pickleball.
      </p>

      {membershipLoading && (
        <p>Loading membership plans...</p>
      )}

      {membershipError && (
        <p>{membershipError}</p>
      )}

      {!membershipLoading && !membershipError && (
        <div className="membership-plans-grid">
          {membershipPlans.length > 0 ? (
            membershipPlans.map((plan) => (
              <article className="membership-plan-card" key={plan.id}>
                <span className="membership-plan-label">
                  MEMBERSHIP PLAN
                </span>

                <h3>{plan.name}</h3>

                <div className="membership-plan-price">
                  ₹{Number(plan.price).toLocaleString("en-IN")}
                </div>

                <p>{plan.description}</p>

                <div className="membership-plan-details">
                  <span>{plan.validity_days} Days Validity</span>
                  <span>{plan.included_hours} Playing Hours</span>
                  <span>Badminton + Pickleball</span>
                </div>

                <a
                className="button button-light"
                href={`/my-membership?planId=${plan.id}`}
              >
                Join Membership ↗
              </a>
              </article>
            ))
          ) : (
            <p>Membership plans will be announced soon.</p>
          )}
        </div>
      )}
    </div>

    <div className="membership-decoration" aria-hidden="true">
      <span>♛</span>
      <strong>THE KING</strong>
      <small>ELITE ARENA</small>
    </div>
  </section>

        <section className="contact-section section" id="contact">
          <span className="eyebrow">READY WHEN YOU ARE</span>
          <h2>Your Court. Your Crew. <span>Your Time.</span></h2>
          <p>
            Get in touch with The King Elite Arena for court bookings and
            membership enquiries.
          </p>
          <a className="button button-primary" href="mailto:info@thekingelitearena.com">
            Contact the Arena <span>↗</span>
          </a>
        </section>

        <footer className="site-footer">
          <a className="brand footer-brand" href="#home">
            <span className="brand-mark">K</span>
            <span className="brand-name">
              THE KING
              <strong>ELITE ARENA</strong>
            </span>
          </a>
          <p>Built for the game. Made for champions.</p>
          <span className="copyright">
            © {new Date().getFullYear()} The King Elite Arena
          </span>
        </footer>
      </main>
    );
  }


  export default function App() {
    const path = window.location.pathname;

    if (path === "/admin") {
      return <AdminPage />;
    }

    return (
      <CustomerAuthProvider>
        {path === "/my-membership" ? (
    <MyMembershipPage />
  ) : path === "/my-bookings" ? (
    <MyBookingsPage />
  ) : path === "/book" ? (
    <BookingPage />
  ) : (
    <LandingPage />
  )}
      </CustomerAuthProvider>
    );
  }

