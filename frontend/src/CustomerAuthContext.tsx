
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

const API = "http://127.0.0.1:8000";

export type Customer = {
  id: number;
  full_name: string;
  phone: string;
  is_active: boolean;
};

type CustomerAuthContextType = {
  customer: Customer | null;
  customerToken: string | null;
  authLoading: boolean;
  loginCustomer: (token: string, customer: Customer) => void;
  logoutCustomer: () => void;
  refreshCustomer: () => Promise<void>;
};

const CustomerAuthContext =
  createContext<CustomerAuthContextType | undefined>(undefined);

export function CustomerAuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [customerToken, setCustomerToken] = useState<string | null>(
    () => localStorage.getItem("customer_access_token")
  );

  const [customer, setCustomer] = useState<Customer | null>(null);

  const [authLoading, setAuthLoading] = useState(true);

  async function refreshCustomer() {
    const token = localStorage.getItem("customer_access_token");

    if (!token) {
      setCustomer(null);
      setCustomerToken(null);
      setAuthLoading(false);
      return;
    }

    setAuthLoading(true);

    try {
      const response = await fetch(`${API}/api/customer-auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Customer session expired.");
      }

      const data: Customer = await response.json();

      setCustomer(data);
      setCustomerToken(token);
    } catch {
      localStorage.removeItem("customer_access_token");
      setCustomer(null);
      setCustomerToken(null);
    } finally {
      setAuthLoading(false);
    }
  }

  function loginCustomer(token: string, customerData: Customer) {
    localStorage.setItem("customer_access_token", token);
    setCustomerToken(token);
    setCustomer(customerData);
    setAuthLoading(false);
  }

  function logoutCustomer() {
    localStorage.removeItem("customer_access_token");
    setCustomerToken(null);
    setCustomer(null);
    setAuthLoading(false);
  }

  useEffect(() => {
    void refreshCustomer();
  }, []);

  return (
    <CustomerAuthContext.Provider
      value={{
        customer,
        customerToken,
        authLoading,
        loginCustomer,
        logoutCustomer,
        refreshCustomer,
      }}
    >
      {children}
    </CustomerAuthContext.Provider>
  );
}

export function useCustomerAuth() {
  const context = useContext(CustomerAuthContext);

  if (!context) {
    throw new Error(
      "useCustomerAuth must be used inside CustomerAuthProvider."
    );
  }

  return context;
}
