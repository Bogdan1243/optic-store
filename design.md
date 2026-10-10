# Optic Store - Architecture & Design Master Plan
*Project Status: Advanced Development / Pre-Deployment*

## 💎 Project Vision
A premium, enterprise-grade e-commerce platform built for a luxury eyewear brand. The system goes beyond standard retail by integrating complex medical data routing (prescription lenses) and interactive Augmented Reality (AR) experiences directly into the shopping flow. 

The UI/UX prioritizes minimalism, high-quality imagery, and frictionless user journeys.

---

## 🏗️ Phase 1: Core E-Commerce & Clinical Routing (COMPLETED)
We transformed a standard shopping cart into a robust medical-grade ordering system.

* **Luxury Cart Flow:** Standardized cart additions to `Qty: 1` by default to match high-end retail behavior.
* **Clinical Data Capture:** Implemented a bespoke JavaScript/AJAX modal to capture 7 critical optical measurements:
    * **Right Eye (OD):** Sphere (SPH), Cylinder (CYL), Axis
    * **Left Eye (OS):** Sphere (SPH), Cylinder (CYL), Axis
    * **Pupillary Distance (PD)**
* **Database Integration:** Expanded the `OrderItem` Django model to permanently store clinical variables alongside standard pricing and product foreign keys.
* **Checkout Pipeline:** Successfully wired the custom cart dictionary to pass medical data through the Stripe Checkout session and save it securely to the database upon successful payment.

## ✉️ Phase 2: Automated Communications (COMPLETED)
* **Customer HTML Receipts:** Designed a responsive, mobile-optimized HTML email receipt. It features a clean grid layout with an embedded light-gray data box explicitly outlining the customer's prescription to ensure medical accuracy.
* **Admin Notifications:** Built an automated internal routing system that emails the store administrators immediately upon payment, securely transmitting the raw clinical data for lens manufacturing.

## ✨ Phase 3: The Luxury User Interface (COMPLETED)
* **Product Detail Page (PDP):** Overhauled the UI to feature an oversized "Hero" image layout on a soft background, star rating logic, and a clinical-yet-sleek "Select Lenses" workflow.
* **Landing Page:** Anchored the digital brand to the physical world by integrating a "Boutiques" section. Configured Django's `STATICFILES_DIRS` to properly serve high-resolution imagery of real-world stores (Timișoara, Bucharest, Cluj, Brașov).
* **User Profile:** Developed an elegant, clutter-free Order History table using Bootstrap Accordions. Customers can click "View Details ▾" to smoothly reveal a hidden row containing both the glasses purchased and their specific medical prescription.

## 🪞 Phase 4: AR "Smart Mirror" Try-On (COMPLETED - V1)
* **AI Integration:** Successfully deployed `face-api.js` (TinyFaceDetector & FaceLandmark68Net) to track user facial geometry via webcam in real-time.
* **UI Wrapping:** Enclosed the raw video feed in a "Smart Mirror" cinematic UI—featuring rounded borders, a frosted-glass status indicator pill, and gradient overlays to hide the boundaries of the canvas.
* **Dynamic Scaling:** Built mathematical logic to scale the 2D glasses overlay dynamically based on the user's distance from the camera (calculating Pupillary Distance in pixels).

---

## 🚀 Phase 5: Future Roadmap & Upgrades (NEXT STEPS)

### 1. Augmented Reality Enhancements
* **Path A (Short-Term):** Implement **Linear Interpolation (Lerp)** into the JavaScript loop. This will mathematically smooth the X/Y coordinates of the glasses, removing the current "jitter" and making the 2D overlay feel incredibly stable and premium.
* **Path B (Long-Term):** Migrate from 2D `.png` images to True 3D `.glb` assets. Replace `face-api.js` with Google MediaPipe and Three.js to allow the glasses to wrap around the ears and map to the face even when the user turns their head 90 degrees.

### 2. Deployment Setup
* Migrate the local SQLite database to a production-ready PostgreSQL database.
* Configure `gunicorn` and WSGI for production serving.
* Deploy the application live to **PythonAnywhere**.
* Set up environment variables for the Stripe Secret Key and Email Passwords to ensure security.

### 3. SEO & Performance
* Implement lazy loading for the high-resolution static images.
* Add dynamic meta tags to the Product Detail Pages for better social media sharing (Open Graph tags).

---
*Document maintained by the Development Team.*
