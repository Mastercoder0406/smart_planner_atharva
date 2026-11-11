🚀 Smart Planner: Accessible Navigation System
Dynamic Multi-Objective Route Planning using A* Algorithm
📌 Introduction

Traditional navigation systems focus only on finding the shortest or fastest route. However, these approaches fail to consider whether a route is actually suitable for users with mobility limitations. Real-world urban environments include challenges such as uneven pavements, steep slopes, poor surface quality, temporary obstacles, and weather-based risks.

This project introduces a Smart Accessible Navigation System that generates personalized, safe, and practical routes by integrating real-world accessibility factors into route planning. The system bridges the gap between digital maps and real-world conditions.

🎯 Objectives
Develop a personalized navigation system based on user mobility needs
Incorporate accessibility factors like slope, surface, and obstacles
Integrate real-time and predictive data into route planning
Improve safety and comfort for elderly and differently-abled users
Build a scalable smart-city-ready solution
⚙️ Methodology
🗺️ 1. Graph Construction
Road network built using OpenStreetMap (OSM)
Converted into a graph structure (nodes & edges)
🧠 2. Dynamic Cost Function

Each path segment is assigned a cost using:

Surface type (asphalt, cobblestone, etc.)
Slope (using elevation data)
Weather conditions (via API)
Obstacle risk (real-time + predicted)

👉 Cost Function:

C(e) = Length × Risk × Weather × Path × Slope × Surface
👤 3. User Personalization
User profiles define:
Maximum slope tolerance
Preferred/disliked surfaces
Routes adapt dynamically based on user needs
<img width="1679" height="824" alt="Screenshot 2026-04-01 184634" src="https://github.com/user-attachments/assets/e2447741-a85e-4d8b-a744-ea343426c8b3" />



🤖 4. Machine Learning (Risk Prediction)
Logistic Regression model
Predicts obstacle probability using:
Time of day
Day of week
Historical patterns
🧮 5. Pathfinding Algorithm
A Algorithm (modified)*
Multi-objective optimization:
Distance
Safety
Comfort
Accessibility

<img width="1919" height="861" alt="Screenshot 2026-04-01 191638" src="https://github.com/user-attachments/assets/e4308dcf-2137-4162-b328-8857b895d9e9" />
<img width="448" height="856" alt="Screenshot 2026-04-01 184013" src="https://github.com/user-attachments/assets/abddf5f4-d712-4ede-a98b-9314b91b6be7" />


🏗️ Tech Stack
Layer	Technology
Backend	Flask
Frontend	Leaflet.js
Database	SQLite
Maps Data	OpenStreetMap
ML Model	Logistic Regression
APIs	Weather API, Elevation API
✨ Features
🔍 Personalized route planning
⚠️ Real-time obstacle avoidance
🌧️ Weather-aware routing
♿ Accessibility-focused navigation
📊 Dynamic cost-based path selection
🌍 Map-based interactive UI
📊 Results
Successfully tested in Mumbai/Navi Mumbai region
Generates safer and more practical routes than traditional systems
Avoids:
Steep slopes
Unsafe surfaces
Temporary obstacles
Weather-affected paths

👉 Instead of shortest path → returns most suitable path

🚀 How to Run the Project
1. Clone the Repository
git clone https://github.com/Mastercoder0406/smart_planner.git
cd smart_planner
2. Install Dependencies
pip install -r requirements.txt
3. Run the Application
python app.py
4. Open in Browser
http://localhost:5000


📂 Project Structure
smart_planner/
│── static/            # Frontend assets (CSS, JS)
│── templates/         # HTML pages
│── database/          # SQLite DB
│── models/            # ML model
│── app.py             # Main Flask app
│── requirements.txt
🎯 Advantages
✔️ Personalized navigation (not one-size-fits-all)
✔️ Improves safety for vulnerable users
✔️ Adapts to real-time environmental changes
✔️ Bridges gap between maps and reality
✔️ Scalable for smart city applications
🔮 Future Scope
AI-based obstacle detection using computer vision
Crowd density & traffic-aware routing
Voice navigation for visually impaired users
Integration with smart city infrastructure
Mobile app deployment
📚 References
OpenStreetMap (OSM)
A* Pathfinding Algorithm
Machine Learning for Risk Prediction
Accessibility-aware routing research papers
