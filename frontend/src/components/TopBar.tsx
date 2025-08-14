import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface TopBarProps {
  toggleSidebar: () => void;
}

const TopBar: React.FC<TopBarProps> = ({ toggleSidebar }) => {
  const { user, logout } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);

  const handleLogout = async () => {
    await logout();
    setShowDropdown(false);
  };

  return (
    <header className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
      <div className="flex h-16 items-center justify-between px-4 md:px-6 2xl:px-11">
        <div className="flex items-center gap-2 sm:gap-4">
          <button
            onClick={toggleSidebar}
            className="z-50 block rounded-sm border border-gray-200 bg-white p-1.5 shadow-sm lg:hidden"
          >
            <svg
              className="h-5.5 w-5.5 cursor-pointer text-black"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          
          {/* App Logo and Name */}
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-md flex items-center justify-center text-white font-bold text-sm bg-brand-500">
              S
            </div>
            <h1 className="text-xl font-bold hidden sm:block text-brand-600">
              Social Media Manager
            </h1>
          </div>
        </div>

        <div className="hidden sm:block">
          <div className="relative">
            <button className="absolute left-0 top-1/2 -translate-y-1/2">
              <svg
                className="h-5 w-5 text-gray-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </button>
            <input
              type="text"
              placeholder="Search posts, ideas..."
              className="w-full bg-transparent pl-9 pr-4 font-medium focus:outline-none xl:w-125 border-b border-transparent focus:border-brand-500 transition-colors"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 2xsm:gap-7">
          {/* Notifications */}
          <div className="relative">
            <button className="relative flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 bg-gray-50 hover:text-brand-600">
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 17h5l-5-5V3a1 1 0 00-1-1h-4a1 1 0 00-1 1v9l-5 5h5"
                />
              </svg>
              <span className="absolute -top-0.5 -right-0.5 z-10 h-2 w-2 rounded-full bg-red-500">
                <span className="absolute z-0 inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75"></span>
              </span>
            </button>
          </div>

          {/* User Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-4"
            >
              <span className="hidden text-right lg:block">
                <span className="block text-sm font-medium text-gray-900">
                  {user ? `${user.first_name} ${user.last_name}`.trim() || 'User' : 'User'}
                </span>
                <span className="block text-xs text-gray-500">
                  Social Media Manager
                </span>
              </span>
              
              <span className="h-12 w-12 rounded-full flex items-center justify-center bg-brand-500">
                <span className="text-white font-medium text-lg">
                  {user?.first_name?.charAt(0) || 'U'}
                </span>
              </span>

              <svg
                className="hidden fill-current sm:block"
                width="12"
                height="8"
                viewBox="0 0 12 8"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M0.410765 0.910734C0.736202 0.585297 1.26384 0.585297 1.58928 0.910734L6.00002 5.32148L10.4108 0.910734C10.7362 0.585297 11.2638 0.585297 11.5893 0.910734C11.9147 1.23617 11.9147 1.76381 11.5893 2.08924L6.58928 7.08924C6.26384 7.41468 5.7362 7.41468 5.41077 7.08924L0.410765 2.08924C0.0853277 1.76381 0.0853277 1.23617 0.410765 0.910734Z"
                  fill=""
                />
              </svg>
            </button>

            {showDropdown && (
              <div
                className="absolute right-0 mt-4 flex w-64 flex-col rounded-sm border border-gray-200 bg-white shadow-lg"
                onBlur={() => setShowDropdown(false)}
              >
                <ul className="flex flex-col gap-5 border-b border-gray-200 px-6 py-8">
                  <li>
                    <button className="flex items-center gap-3.5 text-sm font-medium duration-300 ease-in-out hover:text-brand-600 lg:text-base">
                      <svg
                        className="fill-current"
                        width="22"
                        height="22"
                        viewBox="0 0 22 22"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M11 9.62499C8.42188 9.62499 6.35938 7.59687 6.35938 5.03124C6.35938 2.46562 8.42188 0.437493 11 0.437493C13.5781 0.437493 15.6406 2.46562 15.6406 5.03124C15.6406 7.59687 13.5781 9.62499 11 9.62499ZM11 2.06249C9.28125 2.06249 7.98438 3.32812 7.98438 5.03124C7.98438 6.73437 9.28125 7.99999 11 7.99999C12.7188 7.99999 14.0156 6.73437 14.0156 5.03124C14.0156 3.32812 12.7188 2.06249 11 2.06249Z"
                          fill=""
                        />
                        <path
                          d="M17.7719 21.4156H4.2281C3.5406 21.4156 2.9906 20.8656 2.9906 20.1781V17.0844C2.9906 13.7156 5.7406 10.9656 9.10935 10.9656H12.925C16.2937 10.9656 19.0437 13.7156 19.0437 17.0844V20.1781C19.0437 20.8656 18.4937 21.4156 17.7719 21.4156ZM4.60935 19.8406H16.4219V17.0844C16.4219 15.1656 14.8437 13.5875 12.925 13.5875H9.07498C7.15623 13.5875 5.57811 15.1656 5.57811 17.0844V19.8406H4.60935Z"
                          fill=""
                        />
                      </svg>
                      My Profile
                    </button>
                  </li>
                  <li>
                    <button className="flex items-center gap-3.5 text-sm font-medium duration-300 ease-in-out hover:text-brand-600 lg:text-base">
                      <svg
                        className="fill-current"
                        width="22"
                        height="22"
                        viewBox="0 0 22 22"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M17.6687 1.44374C17.1187 0.893744 16.4312 0.618744 15.675 0.618744H7.42498C6.25623 0.618744 5.25935 1.58124 5.25935 2.78437V4.12499H4.29685C3.88435 4.12499 3.54998 4.45937 3.54998 4.87187C3.54998 5.28437 3.88435 5.61874 4.29685 5.61874H5.25935V10.2781H4.29685C3.88435 10.2781 3.54998 10.6125 3.54998 11.025C3.54998 11.4375 3.88435 11.7719 4.29685 11.7719H5.25935V16.4312H4.29685C3.88435 16.4312 3.54998 16.7656 3.54998 17.1781C3.54998 17.5906 3.88435 17.925 4.29685 17.925H5.25935V19.2656C5.25935 20.4687 6.22185 21.4312 7.42498 21.4312H15.675C17.2218 21.4312 18.5343 20.1187 18.5343 18.5719V3.47812C18.5343 2.68437 18.2593 1.95937 17.6687 1.44374ZM16.9437 18.5719C16.9437 19.2594 16.3937 19.8094 15.7062 19.8094H7.42498C7.0406 19.8094 6.72185 19.4906 6.72185 19.1062V2.78437C6.72185 2.39999 7.0406 2.08124 7.42498 2.08124H15.675C16.0593 2.08124 16.3781 2.20624 16.5562 2.38437C16.7343 2.56249 16.8593 2.88124 16.8593 3.47812V18.5719H16.9437Z"
                          fill=""
                        />
                      </svg>
                      Settings
                    </button>
                  </li>
                </ul>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-3.5 py-4 px-6 text-sm font-medium duration-300 ease-in-out hover:text-brand-600 lg:text-base"
                >
                  <svg
                    className="fill-current"
                    width="22"
                    height="22"
                    viewBox="0 0 22 22"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M15.5375 0.618744H11.6531C10.7594 0.618744 10.0031 1.37499 10.0031 2.26874V4.64062C10.0031 5.05312 10.3375 5.38749 10.75 5.38749C11.1625 5.38749 11.4969 5.05312 11.4969 4.64062V2.26874C11.4969 2.16562 11.5844 2.07812 11.6875 2.07812H15.5375C16.3625 2.07812 17.0156 2.73124 17.0156 3.55624V18.4437C17.0156 19.2687 16.3625 19.9219 15.5375 19.9219H11.6531C11.55 19.9219 11.4625 19.8344 11.4625 19.7312V17.3594C11.4625 16.9469 11.1281 16.6125 10.7156 16.6125C10.3031 16.6125 9.96875 16.9469 9.96875 17.3594V19.7312C9.96875 20.625 10.725 21.3812 11.6187 21.3812H15.5031C17.2469 21.3812 18.675 19.9531 18.675 18.2094V3.79062C18.675 2.04687 17.2469 0.618744 15.5375 0.618744Z"
                      fill=""
                    />
                    <path
                      d="M6.05001 11.7563H12.2031C12.6156 11.7563 12.95 11.4219 12.95 11.0094C12.95 10.5969 12.6156 10.2625 12.2031 10.2625H6.08439L8.21564 8.13128C8.52501 7.82191 8.52501 7.2719 8.21564 6.96253C7.90626 6.65316 7.35626 6.65316 7.04689 6.96253L3.67189 10.3375C3.36251 10.6469 3.36251 11.1969 3.67189 11.5063L7.04689 14.8813C7.20001 15.0344 7.40314 15.1125 7.60626 15.1125C7.80939 15.1125 8.01251 15.0344 8.16564 14.8813C8.47501 14.5719 8.47501 14.0219 8.16564 13.7125L6.05001 11.7563Z"
                      fill=""
                    />
                  </svg>
                  Log Out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default TopBar;