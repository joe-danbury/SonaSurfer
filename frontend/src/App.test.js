import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the SonaSurfer title', () => {
  render(<App />);
  const title = screen.getByText(/SonaSurfer/i);
  expect(title).toBeInTheDocument();
});
