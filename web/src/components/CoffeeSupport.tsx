import React, { useEffect, useRef } from 'react';

export const CoffeeSupport: React.FC<{onClose: () => void}> = ({onClose}) => {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => { if (previousFocus?.isConnected) previousFocus.focus(); };
  }, []);

  return <dialog className="coffee-dialog" ref={dialog} aria-labelledby="coffee-title" aria-describedby="coffee-description" onCancel={onClose}
    onClick={event => {
      if (event.target !== event.currentTarget) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
    }}>
    <button className="coffee-close icon-button" aria-label="Close coffee support" onClick={onClose} autoFocus>×</button>
    <span className="coffee-cup" aria-hidden="true">☕</span>
    <p className="eyebrow">A little warmth for the ice</p>
    <h2 id="coffee-title">Buy me a coffee.</h2>
    <p id="coffee-description">Enjoying Zaya? Support Zaya’s development with an optional contribution through eSewa.</p>
    <figure className="coffee-qr"><img src="/assets/support/esewa-qr.jpeg" alt="eSewa payment QR for supporting Zaya" width="467" height="450" /><figcaption>Scan with eSewa · Choose your amount</figcaption></figure>
    <p className="coffee-payment-note">Check the recipient shown in eSewa before confirming. Contributions are voluntary and do not purchase a service or subscription.</p>
    <a className="btn btn-primary" href="/assets/support/esewa-qr.jpeg" download="zaya-esewa-support.jpeg">Save QR image <span aria-hidden="true">↓</span></a>
    <p className="coffee-thanks">Thank you for helping Zaya grow. ♡</p>
  </dialog>;
};
