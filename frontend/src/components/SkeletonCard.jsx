import './SkeletonCard.css';

export default function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton-card__label" />
      <div className="skeleton-card__value" />
    </div>
  );
}
