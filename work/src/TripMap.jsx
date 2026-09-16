import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { spreadMapLabels } from './map-labels';
export default function TripMap({ stops, focusRequest }) {
  const container = useRef(null);
  const mapState = useRef(null);
  const [tilesFailed, setTilesFailed] = useState(false);
  useEffect(() => {
    if (!stops.length) return;
    setTilesFailed(false);
    const map = L.map(container.current, { scrollWheelZoom: false }).setView([9.965, 76.25], 14);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    tiles.on('tileerror', () => setTilesFailed(true));
    const points = stops.map((s) => [s.place.lat, s.place.lng]);
    const markers = stops.map((stop, index) => {
      const popup = document.createElement('span');
      popup.textContent = `${stop.number ?? index + 1}. ${stop.place.name}`;
      return L.marker(points[index], {
        icon: L.divIcon({
          className: 'number-pin',
          html: `<span>${stop.number ?? index + 1}</span>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        }),
        title: `${stop.number ?? index + 1}. ${stop.place.name}`,
      })
        .bindPopup(popup)
        .addTo(map);
    });
    L.polyline(points, { color: '#246140', weight: 3, dashArray: '6 8' }).addTo(map);
    map.fitBounds(L.latLngBounds(points), { padding: [35, 35], maxZoom: 15 });
    mapState.current = { map, markers, points };
    const connectors = L.layerGroup().addTo(map);
    const positionLabels = () => {
      connectors.clearLayers();
      const pixels = points.map((point) => map.latLngToLayerPoint(point));
      const labels = spreadMapLabels(pixels);
      labels.forEach((pixel, index) => {
        const position = map.layerPointToLatLng(L.point(pixel.x, pixel.y));
        markers[index].setLatLng(position);
        if (Math.hypot(pixel.x - pixels[index].x, pixel.y - pixels[index].y) > 1) {
          L.polyline([points[index], position], {
            color: '#246140',
            weight: 1,
            interactive: false,
          }).addTo(connectors);
        }
      });
    };
    map.on('zoomend moveend', positionLabels);
    positionLabels();
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      mapState.current = null;
      map.remove();
    };
  }, [stops]);
  useEffect(() => {
    const state = mapState.current;
    const index = stops.findIndex((stop) => stop.id === focusRequest?.stopId);
    if (!state || index < 0) return;
    state.map.setView(state.points[index], 15, { animate: false });
    state.markers[index].openPopup();
  }, [focusRequest, stops]);
  return (
    <section
      id="itinerary-map"
      tabIndex={-1}
      className="map-card"
      aria-label="Map of itinerary stops"
    >
      <div ref={container} className="trip-map" />
      <p>
        {tilesFailed
          ? 'Map tiles unavailable. Stops are listed in the timeline.'
          : stops.length
            ? 'Explore your stops here. Choose View in Google Maps to find a place by name and get directions.'
            : 'No stops scheduled for this day.'}
      </p>
    </section>
  );
}
