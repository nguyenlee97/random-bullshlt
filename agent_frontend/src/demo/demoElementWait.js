export function waitForDemoElement(
  selector,
  {
    timeout = 30000,
    interval = 200,
    querySelector = value => document.querySelector(value),
  } = {},
) {
  return new Promise(resolve => {
    const startedAt = Date.now()
    const poll = () => {
      const element = querySelector(selector)
      if (element) {
        resolve(element)
      } else if (Date.now() - startedAt >= timeout) {
        resolve(null)
      } else {
        setTimeout(poll, interval)
      }
    }
    poll()
  })
}
