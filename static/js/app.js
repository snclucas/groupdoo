document.addEventListener('DOMContentLoaded', function () {
  const body = document.body;
  const isAuthenticated = body.dataset.isAuthenticated === 'true';
  const bannerCheckUrl = body.dataset.bannerCheckUrl;
  const bannerAcceptUrl = body.dataset.bannerAcceptUrl;

  const consentBanner = document.getElementById('gdprConsentBanner');
  const acceptBtn = document.getElementById('gdprAccept');
  const dismissBtn = document.getElementById('gdprDismiss');

  function showBanner() {
    if (!consentBanner) {
      return;
    }
    setTimeout(() => {
      consentBanner.classList.add('show');
    }, 500);
  }

  function hideBanner() {
    if (!consentBanner) {
      return;
    }
    consentBanner.classList.remove('show');
  }

  function getCSRFToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
      return metaTag.getAttribute('content');
    }
    return '';
  }

  function checkConsent() {
    if (!consentBanner) {
      return;
    }
    if (isAuthenticated && bannerCheckUrl) {
      fetch(bannerCheckUrl)
        .then(response => response.json())
        .then(data => {
          if (!data.accepted) {
            showBanner();
          }
        })
        .catch(error => console.error('Error checking consent:', error));
      return;
    }

    const localConsent = localStorage.getItem('groupdoo_gdpr_banner_consent');
    if (!localConsent) {
      showBanner();
    }
  }

  if (acceptBtn) {
    acceptBtn.addEventListener('click', function () {
      if (isAuthenticated && bannerAcceptUrl) {
        fetch(bannerAcceptUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
          }
        })
          .then(response => response.json())
          .then(() => {
            hideBanner();
          })
          .catch(error => console.error('Error saving consent:', error));
      } else {
        localStorage.setItem('groupdoo_gdpr_banner_consent', 'accepted');
        hideBanner();
      }
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener('click', function () {
      localStorage.setItem('groupdoo_gdpr_banner_consent', 'dismissed');
      hideBanner();
    });
  }

  checkConsent();

  const eventDateInput = document.getElementById('event_date');
  if (eventDateInput && window.flatpickr) {
    flatpickr(eventDateInput, {
      dateFormat: 'Y-m-d',
      placeholder: 'Select event date'
    });
  }

  const eventTimeInput = document.getElementById('event_time');
  if (eventTimeInput && window.flatpickr) {
    flatpickr(eventTimeInput, {
      enableTime: true,
      noCalendar: true,
      dateFormat: 'H:i',
      time_24hr: true,
      placeholder: 'Select event time'
    });
  }

  const toasts = document.querySelectorAll('.toast');
  if (window.bootstrap && toasts.length) {
    toasts.forEach(toastElement => {
      const bsToast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
      });
      bsToast.show();
    });
  }
});

