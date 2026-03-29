"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Eye,
  EyeOff,
  Loader2,
  AlertCircle,
  Check,
  X,
  Info,
} from "lucide-react";
import { register } from "@/lib/auth";
import { fadeInUp } from "@/lib/animations";
import LandingNavbar from "@/components/layout/Navbar";

const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
const GST_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;

type FieldErrors = Record<string, string>;

function getPasswordStrength(pw: string): {
  level: "weak" | "medium" | "strong";
  label: string;
  color: string;
  width: string;
} {
  if (pw.length < 8)
    return { level: "weak", label: "Weak", color: "bg-red-500", width: "w-1/3" };
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>_\-+=[\]\\/'`;~]/.test(pw);
  if (hasSpecial)
    return { level: "strong", label: "Strong", color: "bg-emerald-500", width: "w-full" };
  return { level: "medium", label: "Medium", color: "bg-amber-500", width: "w-2/3" };
}

function ValidationIcon({ valid }: { valid: boolean | null }) {
  if (valid === null) return null;
  return valid ? (
    <Check className="h-4 w-4 text-emerald-500" />
  ) : (
    <X className="h-4 w-4 text-red-400" />
  );
}

const inputClass =
  "h-11 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-50 placeholder:text-zinc-500 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50";
const inputWithIconClass =
  "h-11 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 pr-10 text-sm text-zinc-50 placeholder:text-zinc-500 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50";

export default function RegisterPage() {
  const router = useRouter();

  // Form state
  const [legalName, setLegalName] = useState("");
  const [panNumber, setPanNumber] = useState("");
  const [gstNumber, setGstNumber] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<"buyer" | "seller" | "">("");
  const [walletAddress, setWalletAddress] = useState("");

  // UI state
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const markTouched = (field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  };

  // Validation
  const validate = useCallback((): FieldErrors => {
    const errs: FieldErrors = {};
    if (!legalName.trim()) errs.legalName = "Legal name is required";
    if (!PAN_REGEX.test(panNumber)) errs.panNumber = "Invalid PAN format (e.g. ABCDE1234F)";
    if (!GST_REGEX.test(gstNumber)) errs.gstNumber = "Invalid GST format (e.g. 22ABCDE1234F1Z5)";
    if (!email.includes("@")) errs.email = "Valid email is required";
    if (password.length < 8) errs.password = "Minimum 8 characters required";
    if (password !== confirmPassword) errs.confirmPassword = "Passwords do not match";
    if (!role) errs.role = "Please select a role";
    return errs;
  }, [legalName, panNumber, gstNumber, email, password, confirmPassword, role]);

  const handleBlur = (field: string) => {
    markTouched(field);
    const errs = validate();
    setFieldErrors((prev) => ({
      ...prev,
      [field]: errs[field] || "",
    }));
  };

  const isFieldValid = (field: string): boolean | null => {
    if (!touched[field]) return null;
    return !fieldErrors[field];
  };

  const isFormValid =
    legalName.trim().length > 0 &&
    PAN_REGEX.test(panNumber) &&
    GST_REGEX.test(gstNumber) &&
    email.includes("@") &&
    password.length >= 8 &&
    password === confirmPassword &&
    role !== "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setTouched(
        Object.fromEntries(Object.keys(errs).map((k) => [k, true]))
      );
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      await register({
        legal_name: legalName.trim(),
        pan_number: panNumber,
        gst_number: gstNumber,
        email: email.trim().toLowerCase(),
        password,
        role: role as "buyer" | "seller",
        wallet_address: walletAddress.trim() || undefined,
      });
      router.push("/dashboard");
    } catch (err: unknown) {
      const errObj = err as { detail?: string };
      setError(
        errObj?.detail || "Registration failed. Please check your details and try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const pwStrength = getPasswordStrength(password);

  return (
    <>
      <LandingNavbar />
      <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-12">
        {/* Background orbs */}
        <div className="pointer-events-none fixed inset-0">
          <div className="absolute -left-40 top-1/4 h-80 w-80 rounded-full bg-emerald-500/5 blur-[120px]" />
          <div className="absolute -right-40 bottom-1/4 h-96 w-96 rounded-full bg-cyan-500/5 blur-[120px]" />
        </div>

        <motion.div
          variants={fadeInUp}
          initial="hidden"
          animate="visible"
          className="relative w-full max-w-2xl"
        >
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8">
            {/* Progress Steps */}
            <div className="mb-8 flex items-center justify-center gap-2">
              {[
                { num: 1, label: "Account Details" },
                { num: 2, label: "Verification" },
                { num: 3, label: "Dashboard" },
              ].map((step, i) => (
                <div key={step.num} className="flex items-center gap-2">
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                      step.num === 1
                        ? "bg-emerald-500 text-black"
                        : "bg-zinc-700 text-zinc-400"
                    }`}
                  >
                    {step.num}
                  </div>
                  <span
                    className={`hidden text-xs sm:inline ${
                      step.num === 1
                        ? "font-medium text-zinc-50"
                        : "text-zinc-500"
                    }`}
                  >
                    {step.label}
                  </span>
                  {i < 2 && (
                    <div className="mx-1 h-px w-8 bg-zinc-700 sm:w-12" />
                  )}
                </div>
              ))}
            </div>

            {/* Header */}
            <div className="mb-8 text-center">
              <h1 className="text-2xl font-bold text-zinc-50">
                Register Your Enterprise
              </h1>
              <p className="mt-1 text-sm text-zinc-400">
                Join the autonomous B2B trade network
              </p>
            </div>

            {/* Error Alert */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                <p className="text-sm text-red-400">{error}</p>
              </motion.div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="grid gap-5 sm:grid-cols-2">
                {/* Column 1 */}
                <div className="space-y-5">
                  {/* Legal Name */}
                  <div>
                    <label
                      htmlFor="reg-legal-name"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      Legal Name
                    </label>
                    <div className="relative">
                      <input
                        id="reg-legal-name"
                        type="text"
                        placeholder="Acme Textiles Pvt. Ltd."
                        value={legalName}
                        onChange={(e) => setLegalName(e.target.value)}
                        onBlur={() => handleBlur("legalName")}
                        className={inputWithIconClass}
                        required
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2">
                        <ValidationIcon valid={isFieldValid("legalName")} />
                      </span>
                    </div>
                    {touched.legalName && fieldErrors.legalName && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.legalName}
                      </p>
                    )}
                  </div>

                  {/* PAN */}
                  <div>
                    <label
                      htmlFor="reg-pan"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      PAN Number
                    </label>
                    <div className="relative">
                      <input
                        id="reg-pan"
                        type="text"
                        placeholder="ABCDE1234F"
                        maxLength={10}
                        value={panNumber}
                        onChange={(e) =>
                          setPanNumber(e.target.value.toUpperCase())
                        }
                        onBlur={() => handleBlur("panNumber")}
                        className={`${inputWithIconClass} font-mono tracking-wider`}
                        required
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2">
                        <ValidationIcon valid={isFieldValid("panNumber")} />
                      </span>
                    </div>
                    {touched.panNumber && fieldErrors.panNumber && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.panNumber}
                      </p>
                    )}
                  </div>

                  {/* GST */}
                  <div>
                    <label
                      htmlFor="reg-gst"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      GST Number
                    </label>
                    <div className="relative">
                      <input
                        id="reg-gst"
                        type="text"
                        placeholder="22ABCDE1234F1Z5"
                        maxLength={15}
                        value={gstNumber}
                        onChange={(e) =>
                          setGstNumber(e.target.value.toUpperCase())
                        }
                        onBlur={() => handleBlur("gstNumber")}
                        className={`${inputWithIconClass} font-mono tracking-wider`}
                        required
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2">
                        <ValidationIcon valid={isFieldValid("gstNumber")} />
                      </span>
                    </div>
                    {touched.gstNumber && fieldErrors.gstNumber && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.gstNumber}
                      </p>
                    )}
                  </div>

                  {/* Email */}
                  <div>
                    <label
                      htmlFor="reg-email"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      Email
                    </label>
                    <div className="relative">
                      <input
                        id="reg-email"
                        type="email"
                        placeholder="admin@enterprise.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        onBlur={() => handleBlur("email")}
                        className={inputWithIconClass}
                        required
                        autoComplete="email"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2">
                        <ValidationIcon valid={isFieldValid("email")} />
                      </span>
                    </div>
                    {touched.email && fieldErrors.email && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.email}
                      </p>
                    )}
                  </div>
                </div>

                {/* Column 2 */}
                <div className="space-y-5">
                  {/* Password */}
                  <div>
                    <label
                      htmlFor="reg-password"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      Password
                    </label>
                    <div className="relative">
                      <input
                        id="reg-password"
                        type={showPassword ? "text" : "password"}
                        placeholder="Min. 8 characters"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onBlur={() => handleBlur("password")}
                        className={inputWithIconClass}
                        required
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 transition-colors hover:text-zinc-300"
                        tabIndex={-1}
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                    {/* Password strength bar */}
                    {password.length > 0 && (
                      <div className="mt-2">
                        <div className="h-1 w-full rounded-full bg-zinc-700">
                          <div
                            className={`h-1 rounded-full transition-all duration-300 ${pwStrength.color} ${pwStrength.width}`}
                          />
                        </div>
                        <p
                          className={`mt-1 text-xs ${
                            pwStrength.level === "weak"
                              ? "text-red-400"
                              : pwStrength.level === "medium"
                              ? "text-amber-400"
                              : "text-emerald-400"
                          }`}
                        >
                          {pwStrength.label}
                        </p>
                      </div>
                    )}
                    {touched.password && fieldErrors.password && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.password}
                      </p>
                    )}
                  </div>

                  {/* Confirm Password */}
                  <div>
                    <label
                      htmlFor="reg-confirm-password"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      Confirm Password
                    </label>
                    <div className="relative">
                      <input
                        id="reg-confirm-password"
                        type={showConfirmPassword ? "text" : "password"}
                        placeholder="••••••••"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        onBlur={() => handleBlur("confirmPassword")}
                        className={inputWithIconClass}
                        required
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowConfirmPassword(!showConfirmPassword)
                        }
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 transition-colors hover:text-zinc-300"
                        tabIndex={-1}
                      >
                        {showConfirmPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                    {touched.confirmPassword && fieldErrors.confirmPassword && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.confirmPassword}
                      </p>
                    )}
                  </div>

                  {/* Role */}
                  <div>
                    <label
                      htmlFor="reg-role"
                      className="mb-1.5 block text-sm font-medium text-zinc-300"
                    >
                      Role
                    </label>
                    <select
                      id="reg-role"
                      value={role}
                      onChange={(e) =>
                        setRole(e.target.value as "buyer" | "seller" | "")
                      }
                      onBlur={() => handleBlur("role")}
                      className={`${inputClass} appearance-none cursor-pointer`}
                      required
                    >
                      <option value="" className="bg-zinc-800 text-zinc-500">
                        Select your role...
                      </option>
                      <option value="buyer" className="bg-zinc-800 text-zinc-50">
                        Buyer (I purchase goods/services)
                      </option>
                      <option value="seller" className="bg-zinc-800 text-zinc-50">
                        Seller (I supply goods/services)
                      </option>
                    </select>
                    {touched.role && fieldErrors.role && (
                      <p className="mt-1 text-xs text-red-400">
                        {fieldErrors.role}
                      </p>
                    )}
                  </div>

                  {/* Wallet Address */}
                  <div>
                    <label
                      htmlFor="reg-wallet"
                      className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-300"
                    >
                      Algorand Wallet Address
                      <span className="group relative">
                        <Info className="h-3.5 w-3.5 cursor-help text-zinc-500" />
                        <span className="invisible absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 shadow-lg group-hover:visible">
                          You can add this later in settings
                        </span>
                      </span>
                    </label>
                    <input
                      id="reg-wallet"
                      type="text"
                      placeholder="ALGO... (optional)"
                      value={walletAddress}
                      onChange={(e) => setWalletAddress(e.target.value)}
                      className={`${inputClass} font-mono text-xs`}
                    />
                  </div>
                </div>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={!isFormValid || isLoading}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 text-sm font-semibold text-black transition-all hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  "Create Enterprise Account"
                )}
              </button>
            </form>

            {/* Footer */}
            <p className="mt-6 text-center text-sm text-zinc-400">
              Already have an account?{" "}
              <Link
                href="/auth/login"
                className="font-medium text-emerald-500 transition-colors hover:text-emerald-400"
              >
                Sign in
              </Link>
            </p>
          </div>
        </motion.div>
      </div>
    </>
  );
}
