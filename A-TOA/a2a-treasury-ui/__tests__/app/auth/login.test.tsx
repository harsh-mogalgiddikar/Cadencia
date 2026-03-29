import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/auth/login/page";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  usePathname: () => "/auth/login",
}));

describe("Login Page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
  });

  it("renders login form with email and password inputs", () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText("admin@enterprise.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("••••••••")).toBeInTheDocument();
  });

  it("renders 'Welcome back' header", () => {
    render(<LoginPage />);
    expect(screen.getByText("Welcome back")).toBeInTheDocument();
  });

  it("renders Sign In submit button", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("has link to registration page", () => {
    render(<LoginPage />);
    const registerLink = screen.getByText("Register now");
    expect(registerLink.closest("a")).toHaveAttribute("href", "/auth/register");
  });

  it("submits form with correct credentials", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText("admin@enterprise.com"),
      "test@enterprise.com"
    );
    await user.type(screen.getByPlaceholderText("••••••••"), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/auth/login",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "test@enterprise.com",
            password: "password123",
          }),
        })
      );
    });
  });

  it("redirects to /dashboard on successful login", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText("admin@enterprise.com"),
      "test@enterprise.com"
    );
    await user.type(screen.getByPlaceholderText("••••••••"), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows loading state during submission", async () => {
    const user = userEvent.setup();
    // Never-resolving fetch to keep loading state active
    global.fetch = jest.fn(() => new Promise(() => {}));
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText("admin@enterprise.com"),
      "test@test.com"
    );
    await user.type(screen.getByPlaceholderText("••••••••"), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByText("Signing in...")).toBeInTheDocument();
  });

  it("shows error alert on failed login", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Invalid credentials" }),
    });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText("admin@enterprise.com"),
      "bad@test.com"
    );
    await user.type(screen.getByPlaceholderText("••••••••"), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("toggles password visibility", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    const passwordInput = screen.getByPlaceholderText("••••••••");
    expect(passwordInput).toHaveAttribute("type", "password");

    // Click the toggle button (the eye icon button after the password field)
    const toggleButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.getAttribute("tabindex") === "-1");
    await user.click(toggleButtons[0]);

    expect(passwordInput).toHaveAttribute("type", "text");
  });

  it("submit button is disabled when form is empty", () => {
    render(<LoginPage />);
    const submitButton = screen.getByRole("button", { name: /sign in/i });
    expect(submitButton).toBeDisabled();
  });
});
