import "@testing-library/jest-dom";
import React from "react";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  redirect: jest.fn(),
}));

// Mock next/link
jest.mock("next/link", () => {
  return {
    __esModule: true,
    default: ({
      children,
      href,
      ...rest
    }: {
      children: React.ReactNode;
      href: string;
      [key: string]: unknown;
    }) => {
      return React.createElement("a", { href, ...rest }, children);
    },
  };
});

// Mock next/headers
jest.mock("next/headers", () => ({
  cookies: () =>
    Promise.resolve({
      get: jest.fn().mockReturnValue({ value: "mock_jwt_token" }),
      set: jest.fn(),
      delete: jest.fn(),
    }),
}));

// Mock framer-motion (avoid animation issues in tests)
jest.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, prop) => {
        // Return a forwardRef component for any HTML element accessed on motion
        return React.forwardRef(function MotionProxy(
          {
            children,
            ...props
          }: { children?: React.ReactNode; [key: string]: unknown },
          ref: React.Ref<HTMLElement>
        ) {
          // Filter out framer-motion-specific props
          const filteredProps: Record<string, unknown> = {};
          const skipProps = new Set([
            "variants",
            "initial",
            "animate",
            "exit",
            "whileInView",
            "whileHover",
            "whileTap",
            "whileFocus",
            "whileDrag",
            "transition",
            "viewport",
            "layout",
            "layoutId",
            "onAnimationComplete",
            "onAnimationStart",
            "drag",
            "dragConstraints",
            "dragElastic",
            "dragMomentum",
            "dragTransition",
            "onDragStart",
            "onDragEnd",
            "onDrag",
            "custom",
            "inherit",
            "mode",
          ]);
          for (const [key, value] of Object.entries(props)) {
            if (!skipProps.has(key)) {
              filteredProps[key] = value;
            }
          }
          return React.createElement(
            prop as string,
            { ref, ...filteredProps },
            children
          );
        });
      },
    }
  ),
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => children,
  useMotionValue: () => ({ set: jest.fn(), get: jest.fn() }),
  useSpring: (val: unknown) => val,
  useTransform: (val: unknown) => val,
  useInView: () => true,
  useAnimation: () => ({
    start: jest.fn(),
    stop: jest.fn(),
    set: jest.fn(),
  }),
}));
