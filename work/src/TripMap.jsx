import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
export default function TripMap({ stops }) {
  const container = useRef(null);
  const [tilesFailed, setTilesFailed] = useState(false);
  useEffect(() => {
    if (!stops.length) return;
    const map = L.map(container.current, { scrollWheelZoom: false }).setView([9.965, 76.25], 14);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    tiles.on('tileerror', () => setTilesFailed(true));
    const points = stops.map((s) => [s.place.lat, s.place.lng]);
    stops.forEach((stop, index) => {
      const popup = document.createElement('span');
      popup.textContent = `${index + 1}. ${stop.place.name}`;
      L.marker(points[index], {
        icon: L.divIcon({
          className: 'number-pin',
          html: `<span>${index + 1}</span>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        }),
        title: `${index + 1}. ${stop.place.name}`,
      })
        .bindPopup(popup)
        .addTo(map);
    });
    L.polyline(points, { color: '#246140', weight: 3, dashArray: '6 8' }).addTo(map);
    map.fitBounds(L.latLngBounds(points), { padding: [35, 35], maxZoom: 15 });
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      map.remove();
    };
  }, [stops]);
  return (
    <section className="map-card" aria-label="Map of itinerary stops">
      <div ref={container} className="trip-map" />
      <p>
        {tilesFailed
          ? 'Map tiles unavailable. Stops are listed in the timeline.'
          : 'OpenStreetMap · Dashed lines connect stops; they are not road directions.'}
      </p>
    </section>
  );
}
