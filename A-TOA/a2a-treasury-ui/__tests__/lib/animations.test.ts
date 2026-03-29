import { fadeInUp, staggerContainer, scaleIn, fadeIn, fadeInDown, slideInLeft, slideInRight, viewportConfig } from "@/lib/animations";

describe("Animation variants", () => {
  describe("fadeInUp", () => {
    it("has correct hidden state", () => {
      expect(fadeInUp.hidden).toEqual({ opacity: 0, y: 24 });
    });

    it("visible state has opacity 1 and y 0", () => {
      expect(fadeInUp.visible.opacity).toBe(1);
      expect(fadeInUp.visible.y).toBe(0);
    });

    it("has transition duration defined", () => {
      expect(fadeInUp.visible.transition.duration).toBe(0.5);
    });
  });

  describe("fadeInDown", () => {
    it("has correct hidden state with negative y", () => {
      expect(fadeInDown.hidden).toEqual({ opacity: 0, y: -24 });
    });
  });

  describe("fadeIn", () => {
    it("hidden state is only opacity 0", () => {
      expect(fadeIn.hidden).toEqual({ opacity: 0 });
    });

    it("visible state is opacity 1", () => {
      expect(fadeIn.visible.opacity).toBe(1);
    });
  });

  describe("staggerContainer", () => {
    it("has staggerChildren in visible transition", () => {
      expect(staggerContainer.visible.transition.staggerChildren).toBe(0.1);
    });

    it("has empty hidden state", () => {
      expect(staggerContainer.hidden).toEqual({});
    });
  });

  describe("scaleIn", () => {
    it("hidden state has scale 0.95", () => {
      expect(scaleIn.hidden.scale).toBe(0.95);
    });

    it("hidden state has opacity 0", () => {
      expect(scaleIn.hidden.opacity).toBe(0);
    });

    it("visible state has scale 1 and opacity 1", () => {
      expect(scaleIn.visible.opacity).toBe(1);
      expect(scaleIn.visible.scale).toBe(1);
    });
  });

  describe("slideInLeft", () => {
    it("hidden state has x -40", () => {
      expect(slideInLeft.hidden.x).toBe(-40);
    });

    it("visible state has x 0", () => {
      expect(slideInLeft.visible.x).toBe(0);
    });
  });

  describe("slideInRight", () => {
    it("hidden state has x 40", () => {
      expect(slideInRight.hidden.x).toBe(40);
    });

    it("visible state has x 0", () => {
      expect(slideInRight.visible.x).toBe(0);
    });
  });

  describe("viewportConfig", () => {
    it("has once: true", () => {
      expect(viewportConfig.once).toBe(true);
    });

    it("has margin set", () => {
      expect(viewportConfig.margin).toBe("-50px");
    });
  });
});
