import './Spinner.css';

export default function Spinner({ centered = false, className = '' }) {
  return (
    <div
      className={`spinner${centered ? ' spinner--centered' : ''} ${className}`.trim()}
      role="status"
      aria-label="Loading"
    />
  );
}
