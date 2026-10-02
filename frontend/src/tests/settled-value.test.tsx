import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSettledValue } from "@/hooks/useSettledValue";

/**
 * Traverser n'est pas s'arrêter.
 *
 * Ce crochet est éprouvé pour lui-même parce que son mécanisme est
 * l'**annulation** : un test qui n'observe qu'une seule valeur passe tout
 * aussi bien sur une version qui n'annule rien, puisque la valeur unique finit
 * par se poser dans les deux cas. C'est exactement ce qui m'est arrivé.
 */
beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("valeur posée", () => {
  it("ne rend rien tant que rien ne s'est posé", () => {
    const { result } = renderHook(() => useSettledValue(1, 1500));

    expect(result.current).toBeNull();
  });

  it("rend la valeur quand elle a cessé de bouger", () => {
    const { result } = renderHook(() => useSettledValue(1, 1500));

    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(result.current).toBe(1);
  });

  it("saute ce qui n'a été que traversé", () => {
    const { result, rerender } = renderHook(({ page }) => useSettledValue(page, 1500), {
      initialProps: { page: 1 }
    });

    for (const page of [2, 3, 4]) {
      act(() => {
        vi.advanceTimersByTime(300);
      });
      rerender({ page });
    }

    // Le moment qui départage : le minuteur de la **première** page arriverait
    // ici à échéance. S'il n'a pas été annulé, le crochet rend 1 — une page
    // seulement traversée. Sans cette observation, le test passait aussi bien
    // sur une version qui n'annulait rien, puisque la dernière valeur finissait
    // de toute façon par se poser.
    act(() => {
      vi.advanceTimersByTime(700);
    });
    expect(result.current).toBeNull();

    act(() => {
      vi.advanceTimersByTime(900);
    });

    // Une seule valeur retenue : la dernière, celle sur laquelle on s'est
    // arrêté. Les trois autres n'ont jamais existé pour qui lira la suite.
    expect(result.current).toBe(4);
  });
});
