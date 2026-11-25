// Prints where HlmsPbs places its ConstBufferPool base; the library's
// exported thunk says 1008, gz-rendering's compiled plugin expects 944.
#include <OgreHlmsPbs.h>
#include <cstdio>
int main() {
    alignas(64) static char buf[sizeof(Ogre::HlmsPbs)];
    auto* pbs = reinterpret_cast<Ogre::HlmsPbs*>(buf);
    auto* pool = static_cast<Ogre::ConstBufferPool*>(pbs);
    std::printf("sizeof(Hlms)=%zu sizeof(HlmsPbs)=%zu ConstBufferPool offset=%td\n",
                sizeof(Ogre::Hlms), sizeof(Ogre::HlmsPbs),
                reinterpret_cast<char*>(pool) - buf);
}
