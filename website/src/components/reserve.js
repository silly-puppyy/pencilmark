// The space a Plot chart (640 wide, `height` tall, scaled down on narrow screens) will take, reserved on its empty
// container: the charts are drawn after the page loads, and without it the text below would jump when they appear.
export const reserve = (height) => ({minHeight: `min(${height}px, ${((100 * height) / 640).toFixed(1)}vw)`});
