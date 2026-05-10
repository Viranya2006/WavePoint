cmake_minimum_required(VERSION 3.20)
project(WavePointCore VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Find Python and pybind11
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

# Source files for the core library
set(CORE_SOURCES
    src/cpp/gesture_engine.cpp
    src/cpp/gesture_state_machine.cpp
    src/cpp/cursor_smoother.cpp
    src/cpp/input_injector.cpp
    src/cpp/coordinate_mapper.cpp
    src/cpp/thread_safe_queue.cpp
    src/cpp/performance_monitor.cpp
)

set(CORE_HEADERS
    src/cpp/include/gesture_engine.hpp
    src/cpp/include/gesture_state_machine.hpp
    src/cpp/include/cursor_smoother.hpp
    src/cpp/include/input_injector.hpp
    src/cpp/include/coordinate_mapper.hpp
    src/cpp/include/thread_safe_queue.hpp
    src/cpp/include/performance_monitor.hpp
    src/cpp/include/gesture_types.hpp
    src/cpp/include/config.hpp
)

# Create the core static library
add_library(gesture_core STATIC ${CORE_SOURCES} ${CORE_HEADERS})
target_include_directories(gesture_core PUBLIC 
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpp/include
)

# Link Windows libraries
target_link_libraries(gesture_core PUBLIC
    user32
    winmm
)

# Compiler options for performance
if(MSVC)
    target_compile_options(gesture_core PRIVATE
        /O2           # Maximum optimization
        /GL           # Whole program optimization
        /fp:fast      # Fast floating point
        /arch:AVX2    # AVX2 instructions if available
    )
    target_link_options(gesture_core PRIVATE /LTCG)
endif()

# Create the Python module
pybind11_add_module(gesture_mouse_core 
    src/cpp/bindings/python_bindings.cpp
)

target_link_libraries(gesture_mouse_core PRIVATE gesture_core)

# Set output directory for the Python module
set_target_properties(gesture_mouse_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/src/gesture_mouse
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/src/gesture_mouse
)

# Copy to both Release and Debug output directories
foreach(CONFIG_TYPE ${CMAKE_CONFIGURATION_TYPES})
    string(TOUPPER ${CONFIG_TYPE} CONFIG_TYPE_UPPER)
    set_target_properties(gesture_mouse_core PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY_${CONFIG_TYPE_UPPER} ${CMAKE_CURRENT_SOURCE_DIR}/src/gesture_mouse
        RUNTIME_OUTPUT_DIRECTORY_${CONFIG_TYPE_UPPER} ${CMAKE_CURRENT_SOURCE_DIR}/src/gesture_mouse
    )
endforeach()

# Installation
install(TARGETS gesture_mouse_core
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

# Print configuration summary
message(STATUS "")
message(STATUS "WavePoint Core Configuration:")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Python: ${Python3_EXECUTABLE}")
message(STATUS "  pybind11: ${pybind11_VERSION}")
message(STATUS "")
