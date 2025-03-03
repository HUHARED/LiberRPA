// FileName: positionCalculation.ts

export function convertScreenPositionToViewport(
  screenX: number,
  screenY: number
): { elementX: number; elementY: number } {
  console.log("--convertScreenPositionToViewPoint--");

  // console.log("screen.availWidth", screen.availWidth);
  // console.log("screen.availHeight", screen.availHeight);

  // console.log("window.screenX", window.screenX);
  // console.log("window.screenY", window.screenY);
  // console.log("window.scrollX", window.scrollX);
  // console.log("window.scrollY", window.scrollY);

  // console.log("window.outerHeight", window.outerHeight);
  // console.log("window.innerHeight", window.innerHeight);

  // console.log("window.outerWidth", window.outerWidth);
  // console.log("window.innerWidth", window.innerWidth);
  const borderWidth = Math.floor((window.outerWidth - window.innerWidth) / 2);
  // console.log("borderWidth", borderWidth);

  let elementX: number;
  let elementY: number;
  let toolBarHeight: number;

  if (borderWidth === 0) {
    // Maximized window.
    elementX = screenX - borderWidth - window.screenX;
    toolBarHeight = window.outerHeight - window.innerHeight;
  } else if (borderWidth < 0) {
    // Fullscreen.
    /* window.screenY and window.screenX is 8 px greater than than actual postion in my PC. 
    I think it may related with the window.outerHeight and window.innerHeight, like borderWidth is related with window.outerWidth and window.innerWidth. 
    So assign toolBarHeight as (window.outerHeight - window.innerHeight) for using later. */

    elementX = screenX - borderWidth - window.screenX;
    toolBarHeight = Math.floor((window.outerHeight - window.innerHeight) / 2); // It's a negative number, in my PC, it's -8.
  } else {
    // Normal window.
    // The toolbar actual size is less 8 px than (window.outerHeight - window.innerHeight).
    elementX = screenX - borderWidth - window.screenX;
    toolBarHeight = window.outerHeight - window.innerHeight - 8;
  }
  // console.log("toolBarHeight", toolBarHeight);

  if (toolBarHeight > 0) {
    // Maximized or normal window.
    elementY = screenY - toolBarHeight - window.screenY;
  } else {
    // Fullscreen.
    // The line is same with toolBarHeight > 0, but toolBarHeight is a negative number.
    elementY = screenY - toolBarHeight - window.screenY;
  }

  return { elementX: elementX, elementY: elementY };
}

export function convertViewportPositionToScreen(
  elementX: number,
  elementY: number
): { screenX: number; screenY: number } {
  // console.log("--convertViewportPositionToScreen--");
  // console.log("elementX", elementX, "elementY", elementY);

  const borderWidth = Math.floor((window.outerWidth - window.innerWidth) / 2);

  let screenX: number;
  let screenY: number;
  let toolBarHeight: number;

  if (borderWidth === 0) {
    // Maximized window.
    screenX = elementX + window.screenX;

    toolBarHeight = window.outerHeight - window.innerHeight;
  } else if (borderWidth >= 0) {
    // Normal window.
    screenX = elementX + borderWidth + window.screenX;

    // The toolbar actual size is less 8 px.
    toolBarHeight = window.outerHeight - window.innerHeight - 8;
  } else {
    // Fullscreen. borderWidth < 0. In my PC, it's -8.
    screenX = elementX + borderWidth + window.screenX;

    // The toolbar actual size is 0.
    toolBarHeight = 0;
  }
  // console.log("toolBarHeight", toolBarHeight);

  if (toolBarHeight > 0) {
    // Maximized or normal window.
    screenY = elementY + toolBarHeight + window.screenY;
  } else {
    // Fullscreen.
    screenY = elementY;
  }

  return { screenX: screenX, screenY: screenY };
}
