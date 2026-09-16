import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())

HTMLCanvasElement.prototype.getContext = () => ({
  clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {},
  set strokeStyle(value) {}, set lineWidth(value) {},
})
