import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "@/app/auth/register/page";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  usePathname: () => "/auth/register",
}));

describe("Register Page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
  });

  it("renders Register Your Enterprise header", () => {
    render(<RegisterPage />);
    expect(screen.getByText("Register Your Enterprise")).toBeInTheDocument();
  });

  it("renders all form fields", () => {
    render(<RegisterPage />);
    expect(screen.getByPlaceholderText("Acme Textiles Pvt. Ltd.")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("ABCDE1234F")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("22ABCDE1234F1Z5")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("admin@enterprise.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min. 8 characters")).toBeInTheDocument();
  });

  it("has link to login page", () => {
    render(<RegisterPage />);
    const signInLink = screen.getByText("Sign in");
    expect(signInLink.closest("a")).toHaveAttribute("href", "/auth/login");
  });

  describe("PAN Validation", () => {
    it("shows error for invalid PAN", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const panInput = screen.getByPlaceholderText("ABCDE1234F");
      await user.type(panInput, "invalid");
      fireEvent.blur(panInput);
      await waitFor(() => {
        expect(screen.getByText(/Invalid PAN format/i)).toBeInTheDocument();
      });
    });

    it("does not show error for valid PAN", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const panInput = screen.getByPlaceholderText("ABCDE1234F");
      await user.type(panInput, "ABCDE1234F");
      fireEvent.blur(panInput);
      await waitFor(() => {
        expect(screen.queryByText(/Invalid PAN/i)).not.toBeInTheDocument();
      });
    });

    it("auto-uppercases PAN input", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const panInput = screen.getByPlaceholderText("ABCDE1234F");
      await user.type(panInput, "abcde1234f");
      expect(panInput).toHaveValue("ABCDE1234F");
    });
  });

  describe("GST Validation", () => {
    it("shows error for invalid GST", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const gstInput = screen.getByPlaceholderText("22ABCDE1234F1Z5");
      await user.type(gstInput, "bad");
      fireEvent.blur(gstInput);
      await waitFor(() => {
        expect(screen.getByText(/Invalid GST format/i)).toBeInTheDocument();
      });
    });

    it("auto-uppercases GST input", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const gstInput = screen.getByPlaceholderText("22ABCDE1234F1Z5");
      await user.type(gstInput, "22abcde1234f1z5");
      expect(gstInput).toHaveValue("22ABCDE1234F1Z5");
    });
  });

  describe("Password Validation", () => {
    it("shows password strength indicator for weak password", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const passwordInput = screen.getByPlaceholderText("Min. 8 characters");
      await user.type(passwordInput, "weak");
      expect(screen.getByText("Weak")).toBeInTheDocument();
    });

    it("shows Strong for password with special characters and length", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const passwordInput = screen.getByPlaceholderText("Min. 8 characters");
      await user.type(passwordInput, "StrongPass@1234");
      expect(screen.getByText("Strong")).toBeInTheDocument();
    });

    it("shows error when passwords do not match", async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      const passwordInput = screen.getByPlaceholderText("Min. 8 characters");
      const confirmInput = screen.getByPlaceholderText("••••••••");
      await user.type(passwordInput, "Test@12345");
      await user.type(confirmInput, "Different@12345");
      fireEvent.blur(confirmInput);
      await waitFor(() => {
        expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument();
      });
    });
  });

  describe("Role Selection", () => {
    it("renders role select with buyer and seller options", () => {
      render(<RegisterPage />);
      expect(screen.getByText("Select your role...")).toBeInTheDocument();
      expect(screen.getByText(/Buyer/)).toBeInTheDocument();
      expect(screen.getByText(/Seller/)).toBeInTheDocument();
    });
  });

  describe("Form Submission", () => {
    it("submit button is disabled when form is incomplete", () => {
      render(<RegisterPage />);
      const submitButton = screen.getByRole("button", {
        name: /create enterprise account/i,
      });
      expect(submitButton).toBeDisabled();
    });

    it("shows API error on duplicate email", async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        json: async () => ({
          detail: "An enterprise with this email already exists.",
        }),
      });
      const user = userEvent.setup();
      render(<RegisterPage />);

      // Fill out the entire form
      await user.type(
        screen.getByPlaceholderText("Acme Textiles Pvt. Ltd."),
        "Test Corp"
      );
      await user.type(
        screen.getByPlaceholderText("ABCDE1234F"),
        "ABCDE1234F"
      );
      await user.type(
        screen.getByPlaceholderText("22ABCDE1234F1Z5"),
        "22ABCDE1234F1Z5"
      );
      await user.type(
        screen.getByPlaceholderText("admin@enterprise.com"),
        "existing@enterprise.com"
      );
      await user.type(
        screen.getByPlaceholderText("Min. 8 characters"),
        "Test@1234"
      );
      await user.type(screen.getByPlaceholderText("••••••••"), "Test@1234");
      await user.selectOptions(screen.getByRole("combobox"), "buyer");

      await user.click(
        screen.getByRole("button", { name: /create enterprise account/i })
      );

      await waitFor(() => {
        expect(
          screen.getByText("An enterprise with this email already exists.")
        ).toBeInTheDocument();
      });
    });
  });

  it("renders progress steps", () => {
    render(<RegisterPage />);
    expect(screen.getByText("Account Details")).toBeInTheDocument();
    expect(screen.getByText("Verification")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });
});
