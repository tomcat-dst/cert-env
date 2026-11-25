// Minimal MAVSDK smoke test: connect to SITL, wait for autopilot, print telemetry.
#include <mavsdk/mavsdk.hpp>
#include <mavsdk/plugins/telemetry/telemetry.hpp>
#include <chrono>
#include <iostream>
#include <thread>
using namespace mavsdk;
int main(int argc, char** argv) {
    const std::string url = argc > 1 ? argv[1] : "tcpout://127.0.0.1:5760";
    Mavsdk mavsdk{Mavsdk::Configuration{ComponentType::GroundStation}};
    if (mavsdk.add_any_connection(url) != ConnectionResult::Success) { std::cerr << "connect failed\n"; return 1; }
    auto sys = mavsdk.first_autopilot(15.0);
    if (!sys) { std::cerr << "no autopilot within 15s\n"; return 2; }
    std::cout << "autopilot sysid=" << int((*sys)->get_system_id()) << "\n";
    Telemetry tel{*sys};
    std::this_thread::sleep_for(std::chrono::seconds(3));
    auto pos = tel.position();
    std::cout << "lat=" << pos.latitude_deg << " lon=" << pos.longitude_deg << " alt_rel=" << pos.relative_altitude_m << "\n";
    std::cout << "health_all_ok=" << tel.health_all_ok() << " flight_mode=" << tel.flight_mode() << "\n";
    return 0;
}
