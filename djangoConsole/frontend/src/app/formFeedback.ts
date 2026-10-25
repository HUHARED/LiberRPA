// FileName: formFeedback.ts

function revealWithinContainer(target: HTMLElement, container: HTMLElement): void {
  let scrollContainer = target.parentElement;
  while (scrollContainer && container.contains(scrollContainer)) {
    if (
      scrollContainer.scrollHeight > scrollContainer.clientHeight &&
      ["auto", "scroll"].includes(getComputedStyle(scrollContainer).overflowY)
    ) {
      const targetRect = target.getBoundingClientRect();
      const containerRect = scrollContainer.getBoundingClientRect();
      const floatTop = containerRect.top + scrollContainer.clientTop;
      const floatBottom = floatTop + scrollContainer.clientHeight;
      if (targetRect.top < floatTop) {
        scrollContainer.scrollTop += targetRect.top - floatTop;
      } else if (targetRect.bottom > floatBottom) {
        scrollContainer.scrollTop += Math.min(
          targetRect.bottom - floatBottom,
          targetRect.top - floatTop,
        );
      }
    }
    scrollContainer = scrollContainer.parentElement;
  }
}

export function revealFormFeedback(
  container: HTMLElement | undefined,
  errorAlert?: HTMLElement,
  boolScrollPage = false,
): void {
  if (!container) return;

  const target = errorAlert ?? container.querySelector<HTMLElement>(".v-input--error");
  if (!target) return;

  const focusTarget =
    errorAlert ??
    target.querySelector<HTMLElement>(
      "input:not([type='hidden']):not(:disabled), textarea:not(:disabled), select:not(:disabled)",
    );
  focusTarget?.focus({ preventScroll: true });
  if (boolScrollPage) target.scrollIntoView({ block: "nearest" });
  else revealWithinContainer(target, container);
}
