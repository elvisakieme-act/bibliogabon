import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useVisiblePage } from "@/components/reader/useVisiblePage";

/**
 * Quelle page est réellement lue.
 *
 * Le lecteur annonçait « 3 / 3 » dès l'ouverture d'une thèse de trois pages :
 * tous les emplacements se déclarent visibles au premier rendu, et le code
 * retenait le dernier à parler. Ce n'est pas un détail d'affichage — c'est
 * aussi la page enregistrée comme progression de lecture.
 */
describe("page la plus visible", () => {
  beforeEach(() => {
    // Les rapports sont groupés par image pour ne pas rendre à chaque
    // émission d'observateur : le test doit donc pouvoir déclencher l'image.
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("retient la page la plus visible, pas la dernière annoncée", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => useVisiblePage(onChange));

    result.current(1, 0.9);
    result.current(2, 0.2);
    result.current(3, 0.05);

    expect(onChange).toHaveBeenLastCalledWith(1);
  });

  it("suit le lecteur quand il fait défiler", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => useVisiblePage(onChange));

    result.current(1, 0.9);
    result.current(2, 0.1);
    expect(onChange).toHaveBeenLastCalledWith(1);

    result.current(1, 0.1);
    result.current(2, 0.9);
    expect(onChange).toHaveBeenLastCalledWith(2);
  });

  it("ne signale pas deux fois la même page", () => {
    // Chaque signalement enregistre la progression de lecture : les répéter
    // ferait une requête par image pendant tout un défilement.
    const onChange = vi.fn();
    const { result } = renderHook(() => useVisiblePage(onChange));

    result.current(1, 0.9);
    result.current(1, 0.8);
    result.current(1, 0.95);

    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("ignore une page sortie de l'écran", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => useVisiblePage(onChange));

    result.current(1, 0.9);
    result.current(1, 0);
    result.current(2, 0.4);

    expect(onChange).toHaveBeenLastCalledWith(2);
  });
});
