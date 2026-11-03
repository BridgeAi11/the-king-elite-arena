import { useEffect, useState } from "react";
import "./App.css";
import AdminPage from "./AdminPage";
import BookingPage from "./BookingPage";

type Sport = {
  name: string;
  description: string;
  courts: string;
  hourly_rate: number;
  icon: string;
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

const initialSports: Sport[] = [
  {
    name: "Badminton",
    description: "Fast rallies. Better fitness. Bigger wins.",
    courts: "4 courts available",
    hourly_rate: 150,
    icon: "🏸",
  },
  {
    name: "Pickleball",
    description: "A fun, fast-paced game for everyone.",
    courts: "2 courts available",
    hourly_rate: 200,
    icon: "🎾",
  },
];


function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  const [sports, setSports] = useState<Sport[]>(initialSports);
  const [facility, setFacility] = useState<Facility | null>(null);
  const [configError, setConfigError] = useState(false);

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
        setSports(
          data.sports.map((sport) => {
            const isBadminton =
              sport.name.toLowerCase() === "badminton";

            return {
              name: sport.name,
              hourly_rate: sport.hourly_rate,
              is_active: sport.is_active,
              description: isBadminton
                ? "Fast rallies. Better fitness. Bigger wins."
                : "A fun, fast-paced game for everyone.",
              courts: isBadminton
                ? "4 courts available"
                : "2 courts available",
              icon: isBadminton ? "🏸" : "🎾",
            };
          })
        );
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

  const closeMenu = () => setMenuOpen(false);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#home" onClick={closeMenu}>
          <span className="brand-mark">K</span>
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

        <nav className={`navigation ${menuOpen ? "navigation-open" : ""}`}>
          <a href="#sports" onClick={closeMenu}>Sports</a>
          <a href="#pricing" onClick={closeMenu}>Pricing</a>
          <a href="#membership" onClick={closeMenu}>Membership</a>
          <a href="#contact" onClick={closeMenu}>Contact</a>
          <a className="nav-cta" href="#pricing" onClick={closeMenu}>
            Book a Court <span>↗</span>
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
            <a className="button button-primary" href="#pricing">
              Book Your Court <span>↗</span>
            </a>
            <a className="button button-secondary" href="#sports">
              Explore Facilities
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

      <section className="sports-section section" id="sports">
        <div className="section-heading">
          <div>
            <span className="eyebrow">FIND YOUR GAME</span>
            <h2>Choose Your <span>Sport.</span></h2>
          </div>
          <p>
            Bring your friends, sharpen your skills and make every match count.
          </p>
        </div>

        <div className="sports-grid">
          {sports.map((sport) => (
            <article className="sport-card" key={sport.name}>
              <div className="sport-card-top">
                <span className="sport-icon" aria-hidden="true">
                  {sport.icon}
                </span>
                <span className="court-count">{sport.courts}</span>
              </div>
              <h3>{sport.name}</h3>
              <p>{sport.description}</p>
              <div className="sport-card-bottom">
                <div className="price">
                  <strong>₹{sport.hourly_rate}</strong>
                  <span>/ hour</span>
                </div>
                <a
                  className="round-link"
                  href="#pricing"
                  aria-label={`View ${sport.name} pricing`}
                >
                  ↗
                </a>
              </div>
            </article>
          ))}
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
          {sports.map((sport) => (
            <article className="pricing-card" key={sport.name}>
              <span className="pricing-label">{sport.name.toUpperCase()}</span>
              <div className="pricing-amount">
                ₹{sport.hourly_rate}
                <span>/ hour</span>
              </div>
              <p>{sport.courts}</p>
              <a className="button button-primary full-button" href="#contact">
                Booking Coming Soon <span>↗</span>
              </a>
            </article>
          ))}
        </div>
        
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
          <h2>Make Every Game <span>Count.</span></h2>
          <p>
            Become a member and get ready for more court time, more
            consistency and more moments with your team.
          </p>
          <a className="button button-light" href="#contact">
            Memberships Coming Soon <span>↗</span>
          </a>
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
  if (window.location.pathname === "/admin") {
    return <AdminPage />;
  }
  if (window.location.pathname === "/book") {
  return <BookingPage />;
}
  return <LandingPage />;
}
