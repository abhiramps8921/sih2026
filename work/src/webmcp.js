import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
export function usePlannerTool() {
  const navigate = useNavigate();
  useEffect(() => {
    if (!document.modelContext?.registerTool) return;
    const lifecycle = new AbortController();
    try {
      Promise.resolve(
        document.modelContext.registerTool(
          {
            name: 'start_trip_planning',
            title: 'Start planning a Kochi trip',
            description: 'Open the trip preferences screen. Does not generate or save a trip.',
            inputSchema: { type: 'object', properties: {}, additionalProperties: false },
            annotations: { readOnlyHint: false, untrustedContentHint: false },
            execute(input) {
              if (
                !input ||
                typeof input !== 'object' ||
                Array.isArray(input) ||
                Object.keys(input).length
              )
                throw new Error('Expected an empty object.');
              navigate('/plan');
              return { screen: 'trip_preferences', trip_saved: false };
            },
          },
          { signal: lifecycle.signal },
        ),
      ).catch((error) => console.warn('Planner tool unavailable:', error.message));
    } catch (error) {
      console.warn('Planner tool unavailable:', error.message);
    }
    return () => lifecycle.abort();
  }, [navigate]);
}
