# AWD-COORD Web Frontend

![AWD-COORD Header](logo.jpg)

A professional, high-performance web frontend for the **AWD-COORD (Alternate Wetting and Drying - Coordination)** network. This application serves as the user-facing portal and live telemetry dashboard for an autonomous agricultural water-management system designed to help farmers share a single pump fairly, saving 25-50% of water.

## 🌟 Key Features

* **Live Telemetry Dashboard**: A responsive, real-time dashboard that fetches and displays live data (water usage, node statuses, active coordinator) from deployed field sensors.
* **Premium UI/UX**: Designed with a modern, glassmorphism aesthetic, smooth CSS animations (`fade-in-up`), blooming hover shadows, and clean SVG iconography (via Lucide).
* **Graceful Degradation**: Features robust empty states and skeleton loaders when awaiting data source configuration.
* **Scrollspy Navigation**: Dynamic landing page navigation that highlights the active section based on the user's scroll position.
* **Authentication Flow**: Includes a beautifully styled frontend authentication mockup (Login/Register) guarded by route-protection logic.

## 🛠️ Tech Stack

This project is built using a lightweight, dependency-free architecture to ensure blazing fast load times and straightforward deployment on any static hosting service.

* **Markup**: HTML5 (Semantic and accessible)
* **Styling**: Vanilla CSS3 (Custom properties, Grid/Flexbox layouts, Keyframe animations)
* **Logic**: Vanilla JavaScript (ES6+)
* **Iconography**: Lucide Icons (via CDN)

## 📂 Project Structure

```text
📁 Website/
├── index.html       # Landing page (Problem, Solution, Impact)
├── dashboard.html   # Protected live telemetry dashboard (uses <template>)
├── login.html       # Login page 
├── register.html    # Registration page
├── style.css        # Global stylesheet and UI variables
├── ui.js            # Global UI behaviors (Intersection Observers, Scrollspy)
├── app.js           # Dashboard logic, API fetching, and DOM rendering
├── auth.js          # Client-side session and route protection simulation
└── logo.jpg         # Brand logo
```

## 🚀 Setup & Installation

Since this is a static frontend, no complex build steps (like Webpack or Node.js) are required. 

1. **Clone the repository** (or download the files):
   ```bash
   git clone https://github.com/litch07/awd-coord.git
   cd awd-coord
   ```

2. **Serve locally**:
   You must serve the files via a local web server (opening the HTML files directly via `file://` may block module loading or CORS requests for data). 
   If you have Python installed:
   ```bash
   python -m http.server 8080
   ```
   *Navigate to `http://localhost:8080/index.html` in your browser.*

3. **Configure the Data Source**:
   To view live telemetry on the dashboard, open `app.js` and configure the `SHEET_URL` constant with your backend endpoint or Google Apps Script URL that serves the CSV telemetry data.

## 🔐 Authentication Mockup

The system currently uses `sessionStorage` and `localStorage` to simulate a login flow.
* **Default Credentials**: `admin` / `admin`
* *Note: In a production environment, `auth.js` should be replaced with a secure backend authentication system (e.g., JWT).*

## 👥 Team & Acknowledgements

Developed by **Team PhaseShift** for the Microprocessors and Microcontrollers Laboratory Project.
* **University**: United International University (UIU)
* **Department**: Computer Science & Engineering

---
*Empowering Next-Gen Agriculture through smart, autonomous resource sharing.*
