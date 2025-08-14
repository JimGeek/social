import React, { useState } from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

interface DashboardLayoutProps {
  children: React.ReactNode;
  noPadding?: boolean;
}

const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children, noPadding = false }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar toggleSidebar={toggleSidebar} />
        
        <main className={`flex-1 overflow-x-hidden bg-gray-50 ${noPadding ? 'overflow-hidden' : 'overflow-y-auto'}`}>
          <div className={noPadding ? 'h-full' : 'p-4 md:p-6 2xl:p-10'}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;