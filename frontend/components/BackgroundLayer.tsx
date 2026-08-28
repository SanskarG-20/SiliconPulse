import React from 'react';

export const BackgroundLayer: React.FC = () => {
  return (
    <div className="fixed inset-0 z-[-1] overflow-hidden pointer-events-none bg-[#050B1A]">
      {/* Deep void with subtle vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(900px 600px at 20% -10%, rgba(34,211,238,0.08), transparent 60%), radial-gradient(700px 500px at 90% 110%, rgba(232,162,83,0.07), transparent 60%), radial-gradient(600px 400px at 50% 50%, #0E1E32 0%, #050B1A 70%)',
        }}
      />

      {/* Blueprint grid - fab reticle */}
      <div
        className="absolute inset-0 opacity-[0.9] blueprint-grid"
        style={{ maskImage: 'radial-gradient(ellipse at center, black 60%, transparent 85%)' }}
      />
      <div className="absolute inset-0 opacity-[0.4] blueprint-grid-fine" />

      {/* Reticle corners - signature */}
      <div className="absolute top-6 left-6 w-12 h-12 border-l border-t border-[#1C3553]/60 hidden lg:block" />
      <div className="absolute top-6 right-6 w-12 h-12 border-r border-t border-[#1C3553]/60 hidden lg:block" />
      <div className="absolute bottom-6 left-6 w-12 h-12 border-l border-b border-[#1C3553]/60 hidden lg:block" />
      <div className="absolute bottom-6 right-6 w-12 h-12 border-r border-b border-[#1C3553]/60 hidden lg:block" />

      {/* Subtle wafer ring */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] rounded-full border border-[#1C3553]/20 hidden xl:block" style={{ maskImage: 'radial-gradient(circle, black 55%, transparent 70%)' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[720px] h-[720px] rounded-full border border-dashed border-[#22D3EE]/10 hidden xl:block" />

      {/* Noise */}
      <div
        className="absolute inset-0 opacity-[0.018] mix-blend-soft-light"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
};
