import React from 'react';
import logoImage from '../assets/Social-Manager-Logo.png';

interface LogoProps {
  className?: string;
  size?: number;
}

const Logo: React.FC<LogoProps> = ({ className = "", size = 40 }) => {
  return (
    <img
      src={logoImage}
      alt="Social Manager Logo"
      width={size}
      height={size}
      className={className}
      style={{ width: size, height: size }}
    />
  );
};

export default Logo;